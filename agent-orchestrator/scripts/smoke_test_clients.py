"""Minimal live smoke test for ClaudeClient and GitHubClient -- confirms
both wrappers actually work against the real APIs. Uses a trivial prompt to
keep cost negligible. Not part of the automated test suite (real network +
real spend); run manually after touching either client.

Usage:
    python agent-orchestrator/scripts/smoke_test_clients.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.claude_client import ClaudeClient
from spend_ledger import SpendLedger


def main() -> None:
    ledger_path = str(Path(__file__).resolve().parent.parent / "smoke_test_ledger.json")
    ledger = SpendLedger(path=ledger_path)

    print("Calling Claude API with a trivial prompt...")
    client = ClaudeClient(spend_ledger=ledger, run_id="smoke-test")
    result = client.complete(
        system="Reply with exactly one word.",
        messages=[{"role": "user", "content": "Say 'ok'."}],
        max_tokens=10,
        node="smoke_test",
    )
    print(f"  Response: {result!r}")
    print(f"  Ledger total spend: RM{ledger.total_spend_myr():.4f}")
    print(f"  Ledger file: {ledger_path}")


if __name__ == "__main__":
    main()
