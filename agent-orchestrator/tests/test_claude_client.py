"""Pins Architecture AD-6's invariant: ClaudeClient.complete() must log to
SpendLedger before returning, on every call. Uses a fake Anthropic client
so no real API key or network call is needed."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from clients.claude_client import ClaudeClient
from spend_ledger import SpendCapExceeded, SpendLedger


class FakeMessages:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


class FakeAnthropic:
    def __init__(self, response, **kwargs):
        self.messages = FakeMessages(response)


def make_response(text="hello", input_tokens=100, output_tokens=50, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )


@pytest.fixture
def ledger(tmp_path):
    return SpendLedger(path=str(tmp_path / "spend_ledger.json"))


def _client_with_fake_response(ledger, response):
    with patch(
        "clients.claude_client.anthropic.Anthropic",
        lambda **kwargs: FakeAnthropic(response),
    ):
        return ClaudeClient(api_key="fake-key", spend_ledger=ledger)


def test_complete_logs_to_ledger_before_returning(ledger):
    response = make_response(text="a plan", input_tokens=1000, output_tokens=500)
    client = _client_with_fake_response(ledger, response)

    result = client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])

    assert result == "a plan"
    assert ledger.total_spend_myr() > 0
    entries = ledger._load()
    assert entries[0]["input_tokens"] == 1000
    assert entries[0]["output_tokens"] == 500


def test_complete_refuses_call_when_already_over_cap(ledger):
    # Push the ledger over the cap first.
    ledger.record_call(input_tokens=0, output_tokens=30_000_000)  # well over RM100
    assert ledger.can_start_new_run() is False

    response = make_response()
    client = _client_with_fake_response(ledger, response)

    with pytest.raises(SpendCapExceeded):
        client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])

    # No new entry should have been recorded -- the call never happened.
    assert len(ledger._load()) == 1


def test_complete_raises_on_empty_text_content(ledger):
    response = make_response(stop_reason="tool_use")
    response.content = [SimpleNamespace(type="tool_use", text=None)]
    client = _client_with_fake_response(ledger, response)

    with pytest.raises(RuntimeError, match="no text content"):
        client.complete(system="sys", messages=[{"role": "user", "content": "hi"}])

    # Spend is still logged even though the caller gets an error -- the
    # API call happened and cost money regardless of content shape.
    assert ledger.total_spend_myr() > 0


def test_complete_warns_on_truncated_response(ledger, caplog):
    import logging

    response = make_response(stop_reason="max_tokens")
    client = _client_with_fake_response(ledger, response)

    with caplog.at_level(logging.WARNING):
        client.complete(system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=10)

    assert any("truncated" in r.message for r in caplog.records)
