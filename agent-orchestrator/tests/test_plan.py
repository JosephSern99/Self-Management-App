from unittest.mock import MagicMock

import pytest

from nodes.plan import plan
from state import RunState


def fake_claude_client(response_text: str = "a plan"):
    client = MagicMock()
    client.complete.return_value = response_text
    return client


def test_plan_sets_state_plan_from_claude_response():
    client = fake_claude_client("Fix the N+1 query in FinanceController.")
    state = RunState(
        run_id="test-run",
        ticket={"number": 1, "title": "Slow finance page", "body": "It's slow."},
    )

    result = plan(state, client)

    assert result.plan == "Fix the N+1 query in FinanceController."


def test_plan_prompt_includes_issue_number_and_title():
    client = fake_claude_client()
    state = RunState(
        run_id="test-run",
        ticket={"number": 42, "title": "Something slow", "body": "details"},
    )

    plan(state, client)

    sent_message = client.complete.call_args.kwargs["messages"][0]["content"]
    assert "#42" in sent_message
    assert "Something slow" in sent_message


def test_plan_handles_null_body_without_leaking_none_literal():
    client = fake_claude_client()
    state = RunState(
        run_id="test-run",
        ticket={"number": 1, "title": "No description issue", "body": None},
    )

    plan(state, client)

    sent_message = client.complete.call_args.kwargs["messages"][0]["content"]
    assert "None" not in sent_message


def test_plan_handles_missing_number_key():
    client = fake_claude_client()
    state = RunState(run_id="test-run", ticket={"title": "t", "body": "b"})

    plan(state, client)  # must not raise

    sent_message = client.complete.call_args.kwargs["messages"][0]["content"]
    assert "None" not in sent_message


def test_plan_raises_on_non_dict_ticket():
    client = fake_claude_client()
    state = RunState(run_id="test-run", ticket="not a dict")

    with pytest.raises(ValueError, match="must be a dict"):
        plan(state, client)


def test_plan_wraps_claude_failure():
    client = MagicMock()
    client.complete.side_effect = RuntimeError("network error")
    state = RunState(run_id="test-run", ticket={"number": 1, "title": "t", "body": "b"})

    with pytest.raises(RuntimeError, match="Plan's Claude call failed"):
        plan(state, client)
