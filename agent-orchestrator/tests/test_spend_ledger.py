import json

import pytest

from spend_ledger import CAP_MYR, SpendLedger


@pytest.fixture
def ledger_path(tmp_path):
    return str(tmp_path / "spend_ledger.json")


def test_fresh_ledger_has_zero_spend(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    assert ledger.total_spend_myr() == 0.0
    assert ledger.can_start_new_run() is True


def test_record_call_appends_and_computes_cost(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    entry = ledger.record_call(input_tokens=1_000_000, output_tokens=1_000_000)

    # claude-sonnet-5: $2/M input + $10/M output = $12 USD at 4.04 MYR/USD
    assert entry["cost_usd"] == pytest.approx(12.0)
    assert entry["cost_myr"] == pytest.approx(48.48)
    assert ledger.total_spend_myr() == pytest.approx(48.48)

    entries = json.loads(open(ledger_path).read())
    assert len(entries) == 1
    assert entries[0]["input_tokens"] == 1_000_000


def test_can_start_new_run_false_at_or_above_cap(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    # Deliberately overshoot the cap slightly (not an exact half-split) so
    # integer token-count truncation can never land the total just under it.
    tokens_over_cap = int((CAP_MYR * 1.1) / (10.0 * 4.04) * 1_000_000)
    ledger.record_call(input_tokens=0, output_tokens=tokens_over_cap)

    assert ledger.total_spend_myr() >= CAP_MYR
    assert ledger.can_start_new_run() is False


def test_can_start_new_run_true_below_cap(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    ledger.record_call(input_tokens=1000, output_tokens=1000)
    assert ledger.can_start_new_run() is True


def test_corrupt_ledger_raises_instead_of_resetting_to_zero(ledger_path):
    with open(ledger_path, "w") as f:
        f.write("{not valid json")

    ledger = SpendLedger(path=ledger_path)
    with pytest.raises(ValueError, match="Corrupt spend ledger"):
        ledger.total_spend_myr()


def test_unknown_model_raises_instead_of_mispricing(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    with pytest.raises(ValueError, match="No pricing known"):
        ledger.record_call(
            input_tokens=1_000_000, output_tokens=0, model="some-future-model"
        )


def test_negative_token_counts_rejected(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    with pytest.raises(ValueError, match="non-negative"):
        ledger.record_call(input_tokens=-1, output_tokens=0)


def test_ledger_write_is_atomic_no_tmp_file_left_behind(ledger_path):
    from pathlib import Path

    ledger = SpendLedger(path=ledger_path)
    ledger.record_call(input_tokens=100, output_tokens=100)
    tmp_path = Path(ledger_path).with_suffix(".json.tmp")
    assert not tmp_path.exists()


def test_run_id_and_node_recorded(ledger_path):
    ledger = SpendLedger(path=ledger_path)
    entry = ledger.record_call(
        input_tokens=100, output_tokens=100, run_id="run-123", node="plan"
    )
    assert entry["run_id"] == "run-123"
    assert entry["node"] == "plan"


def test_malformed_entry_missing_cost_key_raises(ledger_path):
    import json as _json

    with open(ledger_path, "w") as f:
        _json.dump([{"timestamp": "x", "input_tokens": 1}], f)

    ledger = SpendLedger(path=ledger_path)
    with pytest.raises(ValueError, match="missing 'cost_myr'"):
        ledger.total_spend_myr()


def test_ledger_not_a_list_raises(ledger_path):
    import json as _json

    with open(ledger_path, "w") as f:
        _json.dump({"not": "a list"}, f)

    ledger = SpendLedger(path=ledger_path)
    with pytest.raises(ValueError, match="not a list"):
        ledger.total_spend_myr()
