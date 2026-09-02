"""Self-Review node: the last check before Push. Asks Claude to compare the
finished `state.diff` against `state.plan` and the app's CLAUDE.md
conventions, and records a PASS/FAIL verdict. There is no human approval
gate before Push, so this is the only place that can catch a diff that
technically passed tests but doesn't match what was actually asked for, or
that violates a stated project convention.
"""

import logging

from clients.claude_client import ClaudeClient
from state import RunState

logger = logging.getLogger(__name__)

# Kept short and targeted (not the whole CLAUDE.md) so the review call stays
# cheap -- see Design Notes in spec-1-7. Mirrors the Code style / Service
# Layer / domain-area conventions most likely to matter for a scoped change.
CLAUDE_MD_EXCERPT = """\
## Code style
./vendor/bin/pint  # fix PHP code style (Laravel Pint)

## Service Layer
app/Services/FinanceEntityService.php -- new business logic for finance \
calculations should live here, not in controllers.

## Key Domain Areas
| Area | Controller | Model(s) |
|---|---|---|
| Portfolio / Assets | FinanceController | FinancialEntity (soft deletes) |
| Transactions | TransactionController | Transaction |
| Savings Goals | SavingsGoalController | SavingsGoal |
| Payments / Subscriptions | PaymentController, WebhookController | User (Cashier trait) |
| Expense Prediction | ExpensePredictionController | -- (calls Python script) |
| API Tokens | TokenController | -- (Sanctum) |
"""

SYSTEM_PROMPT = """You are the self-review step of an autonomous coding \
agent. Given a change plan, the git diff that was actually implemented, \
and an excerpt of the project's CLAUDE.md conventions, judge whether the \
diff correctly and fully implements the plan, and whether it follows the \
stated conventions (e.g. business logic placed in the Service Layer, not \
controllers). Respond with a first line of EXACTLY "PASS" if the diff is \
acceptable, or "FAIL: <one-sentence reason>" if it is not -- nothing else \
on that first line. You may add further explanation on following lines, \
but the first line is what gets parsed."""


class SelfReviewRejected(RuntimeError):
    pass


def self_review(state: RunState, claude_client: ClaudeClient, repo_dir: str) -> RunState:
    if not state.diff:
        raise ValueError("Cannot self-review: state.diff is empty")

    user_message = (
        f"Change plan:\n{state.plan}\n\n"
        f"Project conventions (CLAUDE.md excerpt):\n{CLAUDE_MD_EXCERPT}\n\n"
        f"Diff to review:\n{state.diff}"
    )

    try:
        raw_response = claude_client.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1024,
            node="self_review",
        )
    except Exception as exc:
        raise RuntimeError(f"Self-Review's Claude call failed: {exc}") from exc

    first_line = raw_response.strip().splitlines()[0].strip() if raw_response.strip() else ""

    if first_line == "PASS":
        state.review_verdict = "PASS"
        return state

    if first_line.startswith("FAIL:"):
        state.review_verdict = first_line
        logger.warning("Self-Review rejected diff: %s", first_line)
        raise SelfReviewRejected(first_line)

    # Malformed response -- neither a clean PASS nor a well-formed FAIL:
    # reason. Fail closed, since there's no approval gate downstream to
    # catch an ambiguous verdict.
    reason = f"FAIL: Self-Review response was malformed (not PASS or FAIL: <reason>): {raw_response!r}"
    state.review_verdict = reason
    logger.warning("Self-Review returned an unparseable verdict: %r", raw_response)
    raise SelfReviewRejected(reason)
