"""Unit tests for orchestrator.run() -- the six-node sequencing, the
node-boundary Spend Cap gate (AD-8), and the exception-to-outcome mapping.
Every node function and both clients are mocked via unittest.mock.patch, so
these tests require no network, PHP, git, or AWS access."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

import orchestrator
from denylist import ScopeViolation
from nodes.self_review import SelfReviewRejected
from nodes.test import TestsFailedAfterRetries
from run_log import RunLogPersistError


ALL_NODES = ["plan", "locate", "implement", "test", "self_review", "push"]


def make_issue(number=42):
    return {"number": number, "title": "Fix the thing", "body": "the body"}


def _recording_stub(name, call_order):
    def _stub(state, *args, **kwargs):
        call_order.append(name)
        return state
    return _stub


class Harness:
    """Patches every collaborator orchestrator.run() touches, recording the
    order nodes are actually invoked in."""

    def __init__(self, stack, call_order, node_mocks, github_client, ledger, persist_mock):
        self.call_order = call_order
        self.node_mocks = node_mocks
        self.github_client = github_client
        self.ledger = ledger
        self.persist_mock = persist_mock


def build_harness(stack: ExitStack, cap_sequence=None, node_side_effects=None) -> Harness:
    call_order = []
    node_side_effects = node_side_effects or {}

    node_mocks = {}
    # orchestrator.py's module-level name for the test node function is
    # "test_and_retry", not "test" -- everything else matches the node name.
    patch_targets = {
        "plan": "plan",
        "locate": "locate",
        "implement": "implement",
        "test": "test_and_retry",
        "self_review": "self_review",
        "push": "push",
    }
    for node_name, attr_name in patch_targets.items():
        if node_name in node_side_effects:
            mock = MagicMock(side_effect=node_side_effects[node_name])
        else:
            mock = MagicMock(side_effect=_recording_stub(node_name, call_order))
        node_mocks[node_name] = mock
        stack.enter_context(patch(f"orchestrator.{attr_name}", mock))

    github_client = MagicMock()
    github_client.get_issue.return_value = make_issue()
    stack.enter_context(patch("orchestrator.GitHubClient", return_value=github_client))
    stack.enter_context(patch("orchestrator.ClaudeClient", return_value=MagicMock()))

    ledger = MagicMock()
    ledger.total_spend_myr.return_value = 0.0
    if cap_sequence is not None:
        ledger.can_start_new_run.side_effect = cap_sequence
    else:
        ledger.can_start_new_run.return_value = True
    stack.enter_context(patch("orchestrator.SpendLedger", return_value=ledger))

    stack.enter_context(
        patch("orchestrator._resolve_run_log_bucket_name", return_value="test-bucket")
    )
    persist_mock = stack.enter_context(patch("orchestrator.persist_run_log"))

    return Harness(stack, call_order, node_mocks, github_client, ledger, persist_mock)


def test_full_success_runs_all_six_nodes_in_order():
    with ExitStack() as stack:
        h = build_harness(stack)
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "success"
    assert h.call_order == ALL_NODES
    h.github_client.get_issue.assert_called_once_with(42)

    h.persist_mock.assert_called_once()
    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "success"
    assert len(run_log.node_trace) == 6
    assert [entry["node"] for entry in run_log.node_trace] == ALL_NODES


def test_spend_used_reflects_real_ledger_total_on_success():
    # RunState.spend_used is never written by any node itself (ClaudeClient
    # logs real cost straight to SpendLedger, bypassing RunState) -- only
    # the orchestrator sees both, so it must snapshot the real cumulative
    # total into state.spend_used at every node boundary, not leave every
    # persisted RunLog entry at the field's 0.0 default.
    with ExitStack() as stack:
        h = build_harness(stack)
        h.ledger.total_spend_myr.return_value = 0.29
        orchestrator.run(42, repo_dir="/tmp/repo")

    run_log = h.persist_mock.call_args.args[0]
    assert all(entry["spend_used"] == 0.29 for entry in run_log.node_trace)


def test_spend_used_captured_even_when_a_node_fails():
    def raise_violation(state, *args, **kwargs):
        raise ScopeViolation("bad path")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"locate": raise_violation})
        h.ledger.total_spend_myr.return_value = 0.11
        orchestrator.run(42, repo_dir="/tmp/repo")

    run_log = h.persist_mock.call_args.args[0]
    assert [entry["node"] for entry in run_log.node_trace] == ["plan", "locate"]
    # "locate" is the node that actually raised; its own trace entry (added
    # by the except branch) must still carry the real spend at the point
    # of failure, not the field's 0.0 default.
    assert run_log.node_trace[-1]["node"] == "locate"
    assert run_log.node_trace[-1]["spend_used"] == 0.11


def test_cap_exhausted_before_start_aborts_with_no_nodes_run():
    with ExitStack() as stack:
        h = build_harness(stack, cap_sequence=[False])
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "aborted"
    assert h.call_order == []
    h.github_client.get_issue.assert_not_called()
    for mock in h.node_mocks.values():
        mock.assert_not_called()

    h.persist_mock.assert_called_once()
    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "aborted"
    assert run_log.node_trace == []


def test_cap_crossed_mid_run_aborts_before_next_node_not_mid_node():
    # True before start, True before plan/locate/implement/test each run,
    # then False right before self_review is about to start.
    with ExitStack() as stack:
        h = build_harness(stack, cap_sequence=[True, True, True, True, True, False])
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "aborted"
    assert h.call_order == ["plan", "locate", "implement", "test"]
    h.node_mocks["self_review"].assert_not_called()
    h.node_mocks["push"].assert_not_called()

    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "aborted"
    assert [entry["node"] for entry in run_log.node_trace] == [
        "plan",
        "locate",
        "implement",
        "test",
    ]


def test_locate_scope_violation_maps_to_failed():
    def raise_violation(state, *args, **kwargs):
        raise ScopeViolation("hallucinated path")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"locate": raise_violation})
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "failed"
    assert h.call_order == ["plan"]
    h.node_mocks["implement"].assert_not_called()

    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "failed"
    assert "hallucinated path" in run_log.outcome_reason
    assert [entry["node"] for entry in run_log.node_trace] == ["plan", "locate"]

    h.github_client.comment_issue.assert_called_once()
    assert h.github_client.comment_issue.call_args.args[0] == 42


def test_test_exhausts_retries_maps_to_failed():
    def raise_tests_failed(state, *args, **kwargs):
        raise TestsFailedAfterRetries("tests still failing after 3 attempts")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"test": raise_tests_failed})
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "failed"
    assert h.call_order == ["plan", "locate", "implement"]
    h.node_mocks["self_review"].assert_not_called()
    h.node_mocks["push"].assert_not_called()

    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "failed"
    assert "tests still failing" in run_log.outcome_reason


def test_self_review_rejected_maps_to_failed():
    def raise_rejected(state, *args, **kwargs):
        raise SelfReviewRejected("FAIL: diff doesn't match plan")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"self_review": raise_rejected})
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "failed"
    assert h.call_order == ["plan", "locate", "implement", "test"]
    h.node_mocks["push"].assert_not_called()

    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "failed"
    assert "diff doesn't match plan" in run_log.outcome_reason


def test_push_blocked_by_drift_maps_to_failed():
    def raise_violation(state, *args, **kwargs):
        raise ScopeViolation("denylisted path drifted in")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"push": raise_violation})
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "failed"
    assert h.call_order == ["plan", "locate", "implement", "test", "self_review"]

    run_log = h.persist_mock.call_args.args[0]
    assert run_log.outcome == "failed"
    assert "denylisted path drifted in" in run_log.outcome_reason
    h.github_client.comment_issue.assert_called_once()


def test_persist_failure_does_not_mask_real_outcome():
    with ExitStack() as stack:
        h = build_harness(stack)
        h.persist_mock.side_effect = RunLogPersistError("s3 unreachable")
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    # persist_run_log blew up, but run()'s own real outcome must still win.
    assert outcome == "success"
    h.persist_mock.assert_called_once()


def test_persist_run_log_called_exactly_once_on_every_outcome():
    def raise_violation(state, *args, **kwargs):
        raise ScopeViolation("bad path")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"locate": raise_violation})
        orchestrator.run(42, repo_dir="/tmp/repo")

    h.persist_mock.assert_called_once()


def test_success_does_not_send_a_failure_comment():
    with ExitStack() as stack:
        h = build_harness(stack)
        orchestrator.run(42, repo_dir="/tmp/repo")

    # Push itself is mocked here (never actually comments/closes), so the
    # only thing to assert is that orchestrator.run() doesn't ALSO send its
    # own best-effort failure comment on a successful run.
    h.github_client.comment_issue.assert_not_called()


def test_cli_entrypoint_exits_zero_on_success(monkeypatch):
    monkeypatch.setattr(orchestrator, "run", lambda issue_number, repo_dir: "success")
    monkeypatch.setattr("sys.argv", ["orchestrator.py", "--issue", "42"])
    with pytest.raises(SystemExit) as exc_info:
        orchestrator.main()
    assert exc_info.value.code == 0


def test_cli_entrypoint_exits_one_on_failure(monkeypatch):
    monkeypatch.setattr(orchestrator, "run", lambda issue_number, repo_dir: "failed")
    monkeypatch.setattr("sys.argv", ["orchestrator.py", "--issue", "42"])
    with pytest.raises(SystemExit) as exc_info:
        orchestrator.main()
    assert exc_info.value.code == 1


def test_cli_entrypoint_exits_two_on_aborted(monkeypatch):
    monkeypatch.setattr(orchestrator, "run", lambda issue_number, repo_dir: "aborted")
    monkeypatch.setattr("sys.argv", ["orchestrator.py", "--issue", "42"])
    with pytest.raises(SystemExit) as exc_info:
        orchestrator.main()
    assert exc_info.value.code == 2


def test_failing_node_still_gets_a_node_trace_entry():
    def raise_violation(state, *args, **kwargs):
        state.plan = "partial plan before locate blew up"
        raise ScopeViolation("hallucinated path")

    with ExitStack() as stack:
        h = build_harness(stack, node_side_effects={"locate": raise_violation})
        outcome = orchestrator.run(42, repo_dir="/tmp/repo")

    assert outcome == "failed"
    run_log = h.persist_mock.call_args.args[0]
    assert [entry["node"] for entry in run_log.node_trace] == ["plan", "locate"]
    # The failing node's own (partially mutated) state is captured too, not
    # just the exception's string.
    assert run_log.node_trace[-1]["plan"] == "partial plan before locate blew up"
