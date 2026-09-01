"""Plan node: reads the Ticket (a GitHub issue) and produces a written
change plan. First node in the graph -- Locate (nodes/locate.py) turns this
plan into concrete file targets.
"""

from clients.claude_client import ClaudeClient
from state import RunState

SYSTEM_PROMPT = """You are the planning step of an autonomous coding agent \
that resolves a single GitHub issue describing a scalability or \
maintainability gap in a Laravel application. Read the issue and write a \
short, concrete change plan: what the actual problem is, and what change \
would fix it. Do not write code. Do not propose new features or unrelated \
refactors -- scope is strictly the gap the issue describes. Reference the \
issue's content directly rather than writing generically."""


def plan(state: RunState, claude_client: ClaudeClient) -> RunState:
    issue = state.ticket
    if not isinstance(issue, dict):
        raise ValueError(f"state.ticket must be a dict, got {type(issue).__name__}")

    # dict.get(key, default) only substitutes the default when the key is
    # absent -- GitHub returns "body": null for issues opened with no
    # description, so `or` (not a get() default) is required to avoid the
    # literal string "None" leaking into the prompt.
    number = issue.get("number") or "?"
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    user_message = f"Issue #{number}: {title}\n\n{body}"

    try:
        plan_text = claude_client.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1024,
            node="plan",
        )
    except Exception as exc:
        raise RuntimeError(f"Plan's Claude call failed: {exc}") from exc

    state.plan = plan_text
    return state
