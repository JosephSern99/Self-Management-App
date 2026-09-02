from unittest.mock import MagicMock

import pytest

from nodes.self_review import SelfReviewRejected, self_review
from state import RunState


def fake_claude_client(response_text: str = "PASS"):
    client = MagicMock()
    client.complete.return_value = response_text
    return client


def make_state(diff="--- a/foo\n+++ b/foo\n"):
    return RunState(
        run_id="test-run",
        ticket={"number": 1, "title": "t", "body": "b"},
        plan="do the thing",
        diff=diff,
    )


def test_self_review_passes(tmp_path):
    client = fake_claude_client("PASS")
    state = make_state()

    result = self_review(state, client, str(tmp_path))

    assert result is state
    assert result.review_verdict == "PASS"


def test_self_review_fails_and_raises(tmp_path):
    client = fake_claude_client("FAIL: diff adds an unrelated refactor not in the plan")
    state = make_state()

    with pytest.raises(SelfReviewRejected, match="unrelated refactor"):
        self_review(state, client, str(tmp_path))

    assert state.review_verdict.startswith("FAIL:")


def test_self_review_rejects_malformed_verdict(tmp_path):
    client = fake_claude_client("Looks good to me!")
    state = make_state()

    with pytest.raises(SelfReviewRejected, match="malformed"):
        self_review(state, client, str(tmp_path))

    assert state.review_verdict.startswith("FAIL:")


def test_self_review_raises_on_empty_diff(tmp_path):
    client = fake_claude_client()
    state = make_state(diff="")

    with pytest.raises(ValueError, match="diff is empty"):
        self_review(state, client, str(tmp_path))

    client.complete.assert_not_called()


def test_self_review_wraps_claude_failure(tmp_path):
    client = MagicMock()
    client.complete.side_effect = RuntimeError("network error")
    state = make_state()

    with pytest.raises(RuntimeError, match="Self-Review's Claude call failed"):
        self_review(state, client, str(tmp_path))


def test_self_review_sends_diff_and_plan_and_conventions(tmp_path):
    client = fake_claude_client("PASS")
    state = make_state(diff="+ some real diff content")
    state.plan = "a very specific plan"

    self_review(state, client, str(tmp_path))

    sent_message = client.complete.call_args.kwargs["messages"][0]["content"]
    assert "a very specific plan" in sent_message
    assert "some real diff content" in sent_message
    assert "CLAUDE.md" in sent_message or "Service Layer" in sent_message


def test_self_review_accepts_verdict_with_trailing_explanation(tmp_path):
    client = fake_claude_client("PASS\nThe diff matches the plan exactly.")
    state = make_state()

    result = self_review(state, client, str(tmp_path))

    assert result.review_verdict == "PASS"
