---
title: 'Orchestrator Entrypoint: Wire All Six Nodes Into a Runnable Pipeline'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'dd85a103ddf767d6a5cbc9158b221be26e786672'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** All six nodes (Plan, Locate, Implement, Test, Self-Review, Push) exist and are individually tested, but nothing calls them in sequence -- `orchestrator.py` doesn't exist, `bootstrap/run.sh` only logs a placeholder, and nothing installs the Python dependencies (`boto3`, `anthropic`) the nodes need on the EC2 instance. Filing a Ticket currently starts an instance that does nothing.

**Approach:** `orchestrator.py`'s `run(issue_number, repo_dir)` builds a `RunState` from the real GitHub issue, checks the Spend Cap before starting and again before every node (AD-8's node-boundary abort), calls the six nodes in order (Test's existing internal Implement-retry loop is unchanged), records each node into a `RunLog`, and always persists the log to S3 exactly once regardless of outcome (success/failed/aborted). `run.sh` gains a `pip install -r requirements.txt` step and the actual `python3 orchestrator.py --issue "$issue_number"` call in place of the placeholder; `provision_trigger_infra.py`'s first-boot user-data gains `python3-pip`.

## Boundaries & Constraints

**Always:** Spend Cap is checked (`SpendLedger.can_start_new_run()`) before the Run starts at all, and again before each node call -- a cap crossed mid-Run aborts before the *next* node, never mid-node, matching AD-8/FR3 exactly. A `RunLog` is persisted exactly once per Run regardless of how it ends (success, any node's guardrail rejection, exhausted Test retries, or spend-cap abort) -- this is the whole point of Story 1.8 existing. A `persist_run_log()` failure itself must not raise past `run()` uncaught -- log it and still return the Run's real outcome/exit code, since a logging failure shouldn't be indistinguishable from a Run failure to whatever calls this (`run.sh`, exit code -> `$exit_code`).

**Ask First:** Nothing requires a mid-execution human decision -- every failure mode here already has a defined automatic outcome from Stories 1.4-1.8.

**Never:** Do not change the internal Implement/Test retry loop (`nodes/test.py`'s `test_and_retry`) -- call it as-is. Do not add LangGraph as a dependency -- the real graph is a strict linear sequence with no branching beyond Test's own already-self-contained retry loop, so a plain Python function achieves AD-1's "single Python orchestrator process per Run" with less operational risk (no new EC2 pip dependency, no framework surface to debug live) than adding a graph-execution library for a sequence with no actual branches; logged as an explicit architecture deviation from the spine's stated LangGraph paradigm, not a silent one. Do not add a human-in-the-loop approval step anywhere -- explicitly out of scope per FR2/PRD.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full success | Valid issue, all six nodes succeed | `run()` returns `"success"`; RunLog has 6 node_trace entries + `outcome="success"`; issue commented+closed by Push | N/A |
| Cap already exhausted before start | `SpendLedger.can_start_new_run()` is `False` at the very start | No node runs; `run()` returns `"aborted"`; RunLog persisted with `outcome="aborted"`, zero node_trace entries | N/A |
| Cap crossed between nodes | Cap check fails before, say, Self-Review, after Test already ran | Self-Review never runs; `run()` returns `"aborted"`; RunLog has entries for every node that DID run, `outcome="aborted"` | N/A |
| Locate rejects (denylist/hallucination) | `locate()` raises `ScopeViolation` | Implement never runs; `run()` returns `"failed"`; RunLog captures Plan's entry + the rejection reason | N/A |
| Test exhausts retries | `test_and_retry()` raises `TestsFailedAfterRetries` | Self-Review/Push never run; `run()` returns `"failed"`; RunLog captures Plan/Locate/Implement + the failure reason | N/A |
| Self-Review rejects | `self_review()` raises `SelfReviewRejected` | Push never runs; `run()` returns `"failed"`; RunLog records the rejection | N/A |
| Push blocked by drift | `push()` raises `ScopeViolation` (denylist re-check) | Nothing is committed/pushed; `run()` returns `"failed"`; RunLog records the block | N/A |
| RunLog persist itself fails | `persist_run_log()` raises `RunLogPersistError` | Logged (not raised) -- `run()` still returns the Run's real outcome, not swallowed by the logging failure | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/orchestrator.py` -- new: `run(issue_number: int, repo_dir: str = DEFAULT_REPO_DIR) -> str`, `_resolve_run_log_bucket_name(sts_client=None) -> str`, CLI entrypoint (`argparse`, `--issue` required int, `--repo-dir` optional) calling `run()` and `sys.exit(0 if outcome == "success" else 1)`
- `agent-orchestrator/state.py:9-18` -- `RunState` constructed here from the fetched issue dict
- `agent-orchestrator/run_log.py` -- `RunLog`, `persist_run_log`, `RunLogPersistError` (Story 1.8) called at every node boundary and once at the end
- `agent-orchestrator/spend_ledger.py:32,71-72` -- `SpendCapExceeded`, `SpendLedger.can_start_new_run()`; checked before start and before each node per AD-8
- `agent-orchestrator/nodes/plan.py:18` `plan(state, claude_client)`, `nodes/locate.py:67` `locate(state, claude_client, repo_dir)` (raises `ScopeViolation`), `nodes/implement.py:117` `implement(state, claude_client, repo_dir)`, `nodes/test.py:109` `test_and_retry(state, claude_client, repo_dir)` (raises `TestsFailedAfterRetries`), `nodes/self_review.py:53` `self_review(state, claude_client, repo_dir)` (raises `SelfReviewRejected`), `nodes/push.py:69` `push(state, github_client, repo_dir)` (raises `ScopeViolation`) -- call signatures to wire exactly as-is
- `agent-orchestrator/clients/claude_client.py:19-33` `ClaudeClient(spend_ledger=..., run_id=...)`, `agent-orchestrator/clients/github_client.py:38-93` `GitHubClient()`, `.get_issue(issue_number) -> dict`, `.comment_issue(issue_number, body)` -- constructed once each in `run()`
- `agent-orchestrator/scripts/provision_secrets_storage.py:164` -- bucket naming convention `f"{account_id}-agent-orchestrator-run-logs"` to replicate via STS in `_resolve_run_log_bucket_name`
- `agent-orchestrator/bootstrap/run.sh:130-145,186-201` -- amend: add `ensure_python_dependencies()` (mirrors `ensure_composer_dependencies`'s idempotent-if-missing pattern) and replace the placeholder block (lines 190-197) with the real `python3 "$REPO_DIR/agent-orchestrator/orchestrator.py" --issue "$issue_number"` call, capturing its exit code into `run.sh`'s own `exit_code`
- `agent-orchestrator/scripts/provision_trigger_infra.py:227-228` -- amend: add `python3-pip` to the existing `install_with_retry` package line (AL2023 ships `python3` but not always `pip`)
- `agent-orchestrator/requirements.txt` -- no change needed (`boto3`, `anthropic` already listed; `PyGithub` was never actually used -- `github_client.py` uses stdlib `urllib`)
- `agent-orchestrator/tests/test_implement.py`, `tests/test_push.py` -- pattern to mirror: `MagicMock` for both clients, module-level functions patched via `unittest.mock.patch("orchestrator.plan", ...)` etc. for sequencing tests

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/orchestrator.py` -- implement per I/O Matrix -- `run()`, cap checks at start and every node boundary, exception-to-outcome mapping (`ScopeViolation`/`TestsFailedAfterRetries`/`SelfReviewRejected`/`SpendCapExceeded` -> `"failed"` or `"aborted"` as appropriate, anything else -> `"failed"`), `RunLog` recorded at every step and persisted exactly once in all cases, CLI entrypoint
- [x] `agent-orchestrator/bootstrap/run.sh` -- amend -- `ensure_python_dependencies()`, replace the placeholder with the real orchestrator invocation and exit-code propagation
- [x] `agent-orchestrator/scripts/provision_trigger_infra.py` -- amend -- add `python3-pip` to first-boot package install
- [x] `agent-orchestrator/tests/test_orchestrator.py` -- unit tests (all six node functions and both clients mocked via `unittest.mock.patch`) covering every I/O Matrix row: full success sequencing/order, cap-exhausted-before-start, cap-crossed-mid-Run (abort before the next node, not mid-node), each node's guardrail exception mapped to the right outcome, and persist-failure-doesn't-mask-real-outcome

**Acceptance Criteria:**
- Given a valid Ticket and no guardrail rejections, when `run()` executes, then all six nodes run in order (Plan, Locate, Implement, Test, Self-Review, Push) and the Run returns `"success"`.
- Given the Spend Cap is already at/above RM100 before `run()` starts, when `run()` is called, then no node executes and the Run returns `"aborted"`.
- Given the cap is crossed after some nodes have already run, when the next node boundary is reached, then that next node does not execute and the Run returns `"aborted"`.
- Given any node raises its documented guardrail exception, when `run()` catches it, then no later node executes, the Run returns `"failed"`, and the reason is recorded in the `RunLog`.
- Given any outcome, when `run()` finishes, then `persist_run_log()` is called exactly once, and a failure inside that call does not change or mask the Run's actual returned outcome.

## Design Notes

Node-boundary spend checks live in `orchestrator.py`, not inside each node -- `ClaudeClient.complete()` already has its own defense-in-depth check (raises `SpendCapExceeded` if the cap is already crossed when a call is attempted), but AD-8's authoritative per-Run gate is explicitly documented in `claude_client.py`'s own docstring as living in "the orchestrator's node-boundary loop," which is exactly what this builds.

Exception-to-outcome mapping is a fixed table, not inferred: `SpendCapExceeded` (from either the node-boundary check or `ClaudeClient`'s own defense-in-depth) -> `"aborted"`; `ScopeViolation`, `TestsFailedAfterRetries`, `SelfReviewRejected` -> `"failed"`; anything else uncaught from a node -> `"failed"` with the raw exception message, since an unexpected crash is still a Run that didn't complete, not a special case.

On a `"failed"` outcome (not `"aborted"`, and never after a successful Push, which already comments+closes the issue itself), `run()` makes a best-effort `github_client.comment_issue()` call summarizing the failure reason, wrapped in its own `try/except` so a GitHub API hiccup during failure handling can never prevent `finalize()`/`persist_run_log()` from still running -- without this, a failed Run leaves Joseph with zero visibility unless he manually checks S3 or EC2 logs, defeating Story 1.8's whole purpose of a human-inspectable trail. This is a judgment call beyond any single story's literal AC, not a hard requirement -- flagged here rather than silently added.

`_resolve_run_log_bucket_name()` calls STS `get_caller_identity()` once at Run start (same pattern already used by `provision_secrets_storage.py`/`provision_trigger_infra.py`) rather than hardcoding or requiring a config file -- the bucket name is fully determined by the AWS account, which is already required for every other AWS call this process makes.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_orchestrator.py -v` -- expected: all pass, no network/PHP/git/AWS required (every node function and both clients mocked)
- `python -m pytest agent-orchestrator/tests -q` -- expected: full suite passes, no regressions
- `bash -n agent-orchestrator/bootstrap/run.sh` -- expected: no syntax errors (matches Story 1.3's existing lint-before-upload precedent)
- Live smoke test: NOT run in this pass -- requires deploying to real EC2 (next `provision_trigger_infra.py --update`/instance replace, then filing a real throwaway `agent-ready` issue) which is outside this environment; flag to Joseph as the outstanding step before trusting this in production, matching Story 1.6's own precedent of a separate live-verification pass after unit tests.

## Review Outcome

Three parallel review layers (blind-hunter, edge-case-hunter, verification-gap) found six real issues, patched: (1) **security** -- `GitHubClient.push()` could leak the raw PAT into a `GitPushError` message if the credentialed remote-URL step failed, which could then propagate into a public GitHub issue comment via the failure-notification path; fixed with a `_sanitize()` helper redacting the token from any exception string before it's embedded in a raised message. (2) `push()`'s post-push `comment_issue`/`close_issue` calls could make a successful push get reported as "no changes were made" if either raised; now non-fatal, logged only. (3) The orchestrator invocation in `run.sh` had no timeout, risking unbounded EC2 cost on a hang; added `RUN_TIMEOUT=1800`. (4) A failed Python dependency install didn't gate the orchestrator invocation, risking a silent `ImportError` with zero RunLog persisted; now gated. (5) A failing node's state wasn't captured in the RunLog, only the exception text; now `record_node()` runs on every path. (6) `"aborted"` and `"failed"` collapsed to the same exit code; now distinct (0/1/2). Full suite: 114/114 passing after patches, no regressions. Live EC2 smoke test not run (no live AWS/GitHub credentials in this environment) -- flagged as the outstanding step before production trust. Remaining lower-severity findings (no incremental RunLog checkpointing, no shell-level executable test for `run.sh`, aborted outcome doesn't trigger a failure comment, `run_id` not surfaced in logs, duplicated `REPO_DIR` constant, fragile `sed` PAT redaction) logged to `deferred-work.md`.
