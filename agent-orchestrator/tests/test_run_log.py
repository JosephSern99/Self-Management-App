import json

import pytest
from botocore.exceptions import ClientError
from unittest.mock import MagicMock

from run_log import RunLog, RunLogPersistError, persist_run_log
from state import RunState


def make_state(**overrides):
    defaults = dict(
        run_id="test-run",
        ticket={"number": 42, "title": "Fix the thing", "body": "a" * 5000},
        plan="do the thing",
        file_targets=["app/Foo.php"],
        diff="--- a/foo\n+++ b/foo\n",
        test_result={"passed": True, "output": "OK"},
        review_verdict="PASS",
        spend_used=0.42,
    )
    defaults.update(overrides)
    return RunState(**defaults)


def test_record_node_accumulates_trace_per_node():
    run_log = RunLog(run_id="test-run", issue_number=42)
    state = make_state()

    run_log.record_node("plan", state)
    state.diff = "updated diff"
    state.file_targets.append("app/Bar.php")
    state.test_result = {"passed": False, "output": "FAIL"}
    run_log.record_node("implement", state)

    assert len(run_log.node_trace) == 2
    assert run_log.node_trace[0]["node"] == "plan"
    assert run_log.node_trace[0]["diff"] == "--- a/foo\n+++ b/foo\n"
    assert run_log.node_trace[1]["node"] == "implement"
    assert run_log.node_trace[1]["diff"] == "updated diff"

    # First entry must be a defensive copy, unaffected by the later
    # mutation of state.file_targets / state.test_result -- guards against
    # an aliasing regression in record_node()'s list(...)/dict(...) copies.
    assert run_log.node_trace[0]["file_targets"] == ["app/Foo.php"]
    assert run_log.node_trace[0]["test_result"] == {"passed": True, "output": "OK"}
    assert run_log.node_trace[1]["file_targets"] == ["app/Foo.php", "app/Bar.php"]
    assert run_log.node_trace[1]["test_result"] == {"passed": False, "output": "FAIL"}

    for entry in run_log.node_trace:
        assert entry["plan"] == "do the thing"
        assert entry["review_verdict"] == "PASS"
        assert entry["spend_used"] == 0.42
        assert "ticket" not in entry  # never repeat the full ticket body per node


def test_persist_run_log_writes_expected_key_and_body():
    s3_client = MagicMock()
    run_log = RunLog(run_id="test-run", issue_number=42)
    run_log.record_node("plan", make_state())
    run_log.finalize("success")

    key = persist_run_log(run_log, "my-bucket", s3_client=s3_client)

    assert key.startswith("runs/42/")
    assert key.endswith("/run_log.json")
    # runs/{issue_number}/{run_timestamp}/run_log.json
    parts = key.split("/")
    assert parts == ["runs", "42", parts[2], "run_log.json"]

    s3_client.put_object.assert_called_once()
    call = s3_client.put_object.call_args
    assert call.kwargs["Bucket"] == "my-bucket"
    assert call.kwargs["Key"] == key

    body = json.loads(call.kwargs["Body"])
    assert body["run_id"] == "test-run"
    assert body["issue_number"] == 42
    assert body["outcome"] == "success"
    assert len(body["node_trace"]) == 1
    assert body["node_trace"][0]["node"] == "plan"


@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("failed", "test suite failed after 3 retries"),
        ("aborted", "spend cap exceeded"),
    ],
)
def test_persist_run_log_writes_failed_or_aborted_outcome(outcome, reason):
    s3_client = MagicMock()
    run_log = RunLog(run_id="test-run", issue_number=42)
    run_log.record_node("plan", make_state())
    run_log.finalize(outcome, reason=reason)

    persist_run_log(run_log, "my-bucket", s3_client=s3_client)

    body = json.loads(s3_client.put_object.call_args.kwargs["Body"])
    assert body["outcome"] == outcome
    assert body["outcome_reason"] == reason


def test_persist_run_log_wraps_s3_failure():
    s3_client = MagicMock()
    s3_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "bucket missing"}}, "PutObject"
    )
    run_log = RunLog(run_id="test-run", issue_number=42)
    run_log.finalize("success")

    with pytest.raises(RunLogPersistError, match="bucket missing"):
        persist_run_log(run_log, "my-bucket", s3_client=s3_client)


def test_persist_run_log_raises_value_error_without_issue_number():
    s3_client = MagicMock()
    run_log = RunLog(run_id="test-run", issue_number=None)
    run_log.finalize("success")

    with pytest.raises(ValueError, match="issue_number"):
        persist_run_log(run_log, "my-bucket", s3_client=s3_client)

    s3_client.put_object.assert_not_called()


def test_persist_run_log_raises_value_error_without_finalize():
    s3_client = MagicMock()
    run_log = RunLog(run_id="test-run", issue_number=42)
    # finalize() never called -- run_log.outcome is still ""

    with pytest.raises(ValueError, match="finalize"):
        persist_run_log(run_log, "my-bucket", s3_client=s3_client)

    s3_client.put_object.assert_not_called()


def test_persist_run_log_wraps_generic_exception_and_botocore_error():
    from botocore.exceptions import BotoCoreError

    for side_effect in (
        RuntimeError("network unreachable"),
        BotoCoreError(),
    ):
        s3_client = MagicMock()
        s3_client.put_object.side_effect = side_effect
        run_log = RunLog(run_id="test-run", issue_number=42)
        run_log.finalize("success")

        with pytest.raises(RunLogPersistError):
            persist_run_log(run_log, "my-bucket", s3_client=s3_client)


def test_to_json_is_valid_json_with_all_fields():
    run_log = RunLog(run_id="test-run", issue_number=42)
    run_log.record_node("plan", make_state())
    run_log.finalize("success")

    parsed = json.loads(run_log.to_json())
    assert parsed["run_id"] == "test-run"
    assert parsed["issue_number"] == 42
    assert parsed["outcome"] == "success"
    assert len(parsed["node_trace"]) == 1
