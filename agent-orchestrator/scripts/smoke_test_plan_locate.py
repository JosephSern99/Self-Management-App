"""Manual live smoke test for the Plan and Locate nodes together, using a
real Claude call and the real repo's tracked-file list. Not part of the
automated test suite (real network + real spend); run manually after
touching either node.

Usage:
    python agent-orchestrator/scripts/smoke_test_plan_locate.py <repo_dir>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.claude_client import ClaudeClient
from nodes.locate import locate
from nodes.plan import plan
from spend_ledger import SpendLedger
from state import RunState


def main() -> None:
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    ledger_path = str(Path(__file__).resolve().parent.parent / "smoke_test_ledger.json")
    ledger = SpendLedger(path=ledger_path)
    client = ClaudeClient(spend_ledger=ledger, run_id="smoke-test-plan-locate")

    state = RunState(
        run_id="smoke-test-plan-locate",
        ticket={
            "number": 0,
            "title": "FinanceController@home: unindexed per-row query in DataTables action column",
            "body": (
                "FinanceController::home() builds an inline action-button string "
                "per row via a closure for every row in the DataTables query, "
                "with no index on financial_entities(user_id). As the number of "
                "entities grows this will not scale. Add appropriate query "
                "optimization/indexing so the finance home page scales."
            ),
        },
    )

    print("Running plan()...")
    state = plan(state, client)
    print(f"  Plan:\n{state.plan}\n")

    print("Running locate()...")
    state = locate(state, client, repo_dir)
    print(f"  File targets: {state.file_targets}")

    print(f"\nLedger total spend: RM{ledger.total_spend_myr():.4f}")


if __name__ == "__main__":
    main()
