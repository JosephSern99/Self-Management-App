"""Append-only, JSON-backed record of every Claude API call's real cost,
enforcing the RM100 Spend Cap (Architecture AD-8). A corrupted or malformed
ledger file raises rather than silently resetting to zero spend -- that
failure mode would defeat the whole point of the cap. Writes are atomic
(temp file + rename) so a crash mid-write can't corrupt the file.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = os.environ.get(
    "AGENT_ORCHESTRATOR_SPEND_LEDGER_PATH",
    "/opt/agent-orchestrator/spend_ledger.json",
)
CAP_MYR = 100.0

# Verified 2026-09-02 via web search. Not fetched live -- a cost-safety
# check should never itself have a network failure mode.
USD_TO_MYR = 4.04

PRICING_USD_PER_MILLION_TOKENS = {
    "claude-sonnet-5": {"input": 2.0, "output": 10.0},
}
DEFAULT_MODEL = "claude-sonnet-5"


class SpendCapExceeded(RuntimeError):
    pass


class SpendLedger:
    def __init__(self, path: str | None = None):
        self.path = Path(path or DEFAULT_PATH)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Corrupt spend ledger at {self.path}: {exc}. Refusing to "
                "treat this as zero spend -- fix or replace the file "
                "manually before continuing."
            ) from exc
        if not isinstance(data, list):
            raise ValueError(
                f"Spend ledger at {self.path} is valid JSON but not a list "
                f"(got {type(data).__name__}). Refusing to treat this as "
                "zero spend."
            )
        for entry in data:
            if "cost_myr" not in entry:
                raise ValueError(
                    f"Spend ledger entry missing 'cost_myr' in {self.path}: "
                    f"{entry}. Refusing to treat this as zero spend."
                )
        return data

    def total_spend_myr(self) -> float:
        return sum(entry["cost_myr"] for entry in self._load())

    def can_start_new_run(self) -> bool:
        return self.total_spend_myr() < CAP_MYR

    def record_call(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = DEFAULT_MODEL,
        run_id: str | None = None,
        node: str | None = None,
    ) -> dict:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError(
                f"Token counts must be non-negative, got input={input_tokens} "
                f"output={output_tokens}"
            )
        if model not in PRICING_USD_PER_MILLION_TOKENS:
            raise ValueError(
                f"No pricing known for model '{model}'. Add it to "
                "PRICING_USD_PER_MILLION_TOKENS rather than silently "
                "mispricing it against another model's rates."
            )

        pricing = PRICING_USD_PER_MILLION_TOKENS[model]
        cost_usd = (input_tokens / 1_000_000) * pricing["input"] + (
            output_tokens / 1_000_000
        ) * pricing["output"]
        cost_myr = cost_usd * USD_TO_MYR

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "node": node,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6),
            "cost_myr": round(cost_myr, 6),
        }

        entries = self._load()
        entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entries, indent=2))
        tmp_path.replace(self.path)  # atomic on POSIX and Windows

        new_total = sum(e["cost_myr"] for e in entries)
        logger.info(
            "Spend recorded: %s tokens in / %s out, RM%.2f this call, "
            "RM%.2f cumulative (cap RM%.2f)",
            input_tokens,
            output_tokens,
            cost_myr,
            new_total,
            CAP_MYR,
        )
        return entry
