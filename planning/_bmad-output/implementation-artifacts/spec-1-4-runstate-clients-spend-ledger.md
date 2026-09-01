---
title: 'Story 1.4: RunState, Client Wrappers & Spend Ledger'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '4741590e9f0e6ebabdf66886d2886d67b6818eb4'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Stories 1.5–1.7's nodes (Plan/Locate/Implement/Test/Self-Review/Push) all need a shared way to pass data to each other, talk to GitHub and Claude, and enforce the RM100 spend cap — none of that exists yet.

**Approach:** Four small, independently importable Python modules: `state.py` (the `RunState` schema with AD-1's fixed field names), `spend_ledger.py` (append-only JSON-backed spend tracking against the RM100 cap), and `clients/github_client.py` + `clients/claude_client.py` (the two AD-6 wrappers, with `ClaudeClient` logging every call's cost to `SpendLedger` before returning).

## Boundaries & Constraints

**Always:** `RunState` field names exactly match Architecture AD-1: `ticket`, `plan`, `file_targets`, `diff`, `test_result`, `review_verdict`, `spend_used`, `run_id`. `SpendLedger`'s file lives at `/opt/agent-orchestrator/spend_ledger.json` by default but the path is constructor-injectable for testing. Cost is computed from actual `usage.input_tokens`/`usage.output_tokens` on each Claude API response, converted through real per-model USD pricing then to MYR — never estimated from prompt length. `ClaudeClient` logs to `SpendLedger` before returning to its caller (per AD-6), so a caller can never observe a response the ledger doesn't yet reflect.

**Ask First:** Nothing requires a mid-execution human decision.

**Never:** Do not call the raw `anthropic` or `PyGithub`/`urllib` GitHub calls from anywhere outside these two client modules (AD-6) — later stories' nodes must import `GitHubClient`/`ClaudeClient`, never reimplement a call. Do not implement any node logic here (Plan/Locate/etc. are Stories 1.5–1.7). Do not use a live USD/MYR exchange-rate API — a hardcoded, documented rate is fine and avoids an extra external dependency for a cost-safety check that should never itself fail open.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fresh ledger, no prior spend | No `spend_ledger.json` exists yet | `SpendLedger().total_spend_myr()` returns `0.0`; `can_start_new_run()` returns `True` | N/A |
| Cumulative spend at/above cap | Ledger sums to >= RM100 | `can_start_new_run()` returns `False` | N/A |
| Claude API call succeeds | `ClaudeClient.complete(...)` called | Response text returned; ledger gains one new entry with the call's actual token usage and computed MYR cost, timestamped | N/A |
| Ledger file corrupted (invalid JSON) | `spend_ledger.json` exists but isn't valid JSON | `SpendLedger` treats this as a hard stop: raises clearly rather than silently resetting to zero spend (a corrupted-file-means-zero-spend bug would defeat the whole cost cap) | Caller sees a clear exception naming the corrupt file path |
| GitHub issue comment/close on a real issue | Valid issue number, valid PAT | `GitHubClient.comment_issue()`/`close_issue()` succeed against the real API | Non-2xx response raises with the status code and body in the message |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/state.py` -- new: `RunState` dataclass
- `agent-orchestrator/spend_ledger.py` -- new: `SpendLedger` class
- `agent-orchestrator/clients/__init__.py` -- new: package marker
- `agent-orchestrator/clients/claude_client.py` -- new: `ClaudeClient`, wraps `anthropic.Anthropic`, logs to `SpendLedger`
- `agent-orchestrator/clients/github_client.py` -- new: `GitHubClient`, issue read/comment/close + `git push`
- `agent-orchestrator/trigger_lambda/handler.py` -- reference only (Story 1.2): its inline `github_request`/label logic is Lambda-specific and stays there; `GitHubClient` is for the orchestrator's own node code, not a refactor of the Lambda
- `agent-orchestrator/clients/_ssm.py` -- new: shared SSM secret-fetch helper (avoids duplicating the same boto3 call in both clients)
- `agent-orchestrator/scripts/smoke_test_clients.py` -- new: manual live smoke test for `ClaudeClient` (real API, trivial prompt, negligible cost)
- `agent-orchestrator/tests/` -- new: unit tests for `SpendLedger` and `ClaudeClient` (pure logic + mocked Anthropic client, no real network)

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/state.py` -- implement `RunState` per AD-1's field list
- [x] `agent-orchestrator/spend_ledger.py` -- implement per I/O Matrix -- append-only JSON file, `record_call()`, `total_spend_myr()`, `can_start_new_run()`
- [x] `agent-orchestrator/clients/claude_client.py` -- implement `ClaudeClient.complete()`, logging every call's real usage/cost to `SpendLedger` before returning
- [x] `agent-orchestrator/clients/github_client.py` -- implement `get_issue()`, `comment_issue()`, `close_issue()`, `push()`
- [x] `agent-orchestrator/tests/test_spend_ledger.py` -- unit tests covering the I/O Matrix's `SpendLedger` rows (fresh ledger, at-cap, corrupted file), no network/AWS required

**Acceptance Criteria:**
- Given a fresh `SpendLedger` with no prior entries, when a caller checks `can_start_new_run()`, then it returns `True`.
- Given a `SpendLedger` whose recorded entries sum to RM100 or more, when a caller checks `can_start_new_run()`, then it returns `False`.
- Given a real Claude API call through `ClaudeClient.complete()`, when it returns, then `SpendLedger` has one new entry whose cost was computed from that call's actual `usage.input_tokens`/`usage.output_tokens`.
- Given a real GitHub issue, when `GitHubClient.comment_issue()` is called, then the comment appears on the issue via the GitHub API.

## Design Notes

Pricing: Claude Sonnet 5 (`claude-sonnet-5`) at $2/M input tokens, $10/M output tokens (verified via web search, 2026-09-02 — this was Anthropic's introductory rate and was made permanent on 2026-08-10, replacing a planned increase). USD→MYR: 4.04 (verified 2026-09-02), hardcoded as a hardcoded constant near the top of `spend_ledger.py` with a comment noting the verification date, not fetched live (per Boundaries). `ClaudeClient` defaults to `claude-sonnet-5` but accepts a model override so later stories can tune per-node if needed without touching this file again.

`SpendLedger`'s JSON is a simple list of `{timestamp, input_tokens, output_tokens, cost_usd, cost_myr}` entries — append-only, never rewritten or compacted, matching Architecture AD-8.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_spend_ledger.py -v` -- expected: all pass, no network/AWS calls made
- Small live smoke test (run once, minimal cost): a short script calling `ClaudeClient.complete()` with a trivial prompt, then printing `SpendLedger.total_spend_myr()` -- expected: a small positive number, ledger file contains the new entry
- `GitHubClient.comment_issue()` against a real (throwaway) comment on an existing issue, then manually verified in the GitHub UI

## Spec Change Log

- 2026-09-02: Review (2x independently: blind hunter and edge-case hunter) found the RM100 cap was recorded after spend but never checked before it -- `ClaudeClient.complete()` could keep spending past the cap indefinitely. Added a pre-flight `can_start_new_run()` check in `complete()` that raises `SpendCapExceeded` before any API call, as defense-in-depth alongside the future orchestrator-level node-boundary check (AD-8's authoritative gate, not yet built). KEEP: the ledger write is now atomic (temp file + rename) and validates entry shape on load, per the same review pass.
- 2026-09-02: `push()`'s `git push` failure path amended after review to preserve the original error even if the credential-cleanup step also fails (previously the cleanup exception could silently shadow the real push failure). Added a branch check (refuses to push if not on `main`) and an optional `paths` param for future stories to scope staging instead of always `git add -A`.

## Live Verification

Verified 2026-09-02:
- `python -m pytest agent-orchestrator/tests/ -v` -- 15/15 passed (SpendLedger: fresh/at-cap/corrupt-file/malformed-entry/atomic-write/run-id-attribution; ClaudeClient: AD-6 log-before-return ordering, cap-refusal, empty-content handling, truncation warning -- all via a mocked Anthropic client, no real spend).
- `smoke_test_clients.py` -- real Claude API call, response `'ok'`, RM0.0004 logged to the ledger.
- `GitHubClient.get_issue()` / `comment_issue()` / `close_issue()` -- all verified against a real throwaway issue (#1) on the actual repo: title read correctly, comment posted (id `5497832340`), issue closed.
- `GitHubClient.push()` intentionally **not** live-tested here -- doing so would be the first real, unreviewed push to `main`, which is the exact checkpoint reserved for explicit confirmation ahead of Story 1.7. Verified by code review only; live-tested when that gate opens.
