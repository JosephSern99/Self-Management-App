---
title: 'Story 1.8: Run Log Persistence to S3'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '8cf191f893cd78f70fce3f83f8ea979ce8c94e43'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Every node (Plan, Locate, Implement, Test, Self-Review, Push) produces useful output, but nothing durable records it -- once the on-demand EC2 instance stops, a Run's plan, diffs, test output, and outcome are gone.

**Approach:** A new `run_log.py` module: `RunLog` accumulates a per-node trace (`record_node(node_name, state)`) as each node completes, plus a final outcome (`finalize(outcome, reason)`); `persist_run_log()` writes it as one JSON object to `s3://{run-log-bucket}/runs/{issue-number}/{run-timestamp}/run_log.json`. This is a standalone, independently-testable component nodes/orchestrator can call -- it does not itself wire the six nodes together (that's the already-deferred `orchestrator.py` work).

## Boundaries & Constraints

**Always:** `persist_run_log()` must succeed (or raise clearly) regardless of Run outcome -- success, failed, or aborted -- since a failed/aborted Run's log is exactly what a human needs to debug after the fact. The log must be inspectable as plain JSON, readable without the EC2 instance or any other AWS resource existing. Bucket name follows the existing convention from Story 1.1 (`{account_id}-agent-orchestrator-run-logs`, already provisioned) -- do not create a new bucket or hardcode a name; accept it as a parameter.

**Ask First:** Nothing requires a mid-execution human decision.

**Never:** Do not build `orchestrator.py` or wire the six nodes into an actual pipeline here -- already logged as deferred work from Story 1.7; this story only gives that future orchestrator something to call at each node boundary and at the end. Do not invent a new S3 client wrapper class -- follow `clients/_ssm.py`'s existing pattern of a plain boto3 call, since this is a single write operation, not a multi-method service like `GitHubClient`/`ClaudeClient`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal trace | `record_node()` called after each of the six nodes with the current `RunState` | `RunLog.node_trace` has one entry per call, each capturing that node's name and the state fields relevant at that point (plan, diff, test_result, review_verdict, file_targets, spend_used) | N/A |
| Successful Run persisted | `finalize("success")` called, then `persist_run_log()` | Object written to `s3://{bucket}/runs/{issue_number}/{run_timestamp}/run_log.json`, readable back as valid JSON containing every recorded node and the outcome | N/A |
| Failed/aborted Run persisted | `finalize("failed", reason="...")` or `finalize("aborted", reason="...")` | Same as above but with `outcome` and `outcome_reason` reflecting the failure -- log is written exactly the same way, no special-casing | N/A |
| S3 write fails | `s3_client.put_object` raises (e.g. network error, bucket missing) | `persist_run_log()` raises `RunLogPersistError` naming the underlying cause | Run's outcome is not itself changed by a logging failure -- this is a separate concern from the Run's own success/failure |
| No issue number available | `RunLog` constructed with `issue_number=None` | `persist_run_log()` raises `ValueError` before attempting any S3 call -- the key path requires it | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/run_log.py` -- new: `RunLog` (dataclass: `run_id`, `issue_number`, `node_trace: list[dict]`, `outcome: str = ""`, `outcome_reason: str = ""`), `record_node(self, node_name: str, state: RunState) -> None`, `finalize(self, outcome: str, reason: str = "") -> None`, `to_json(self) -> str`; module function `persist_run_log(run_log: RunLog, bucket_name: str, s3_client=None) -> str` (returns the S3 key written), `RunLogPersistError(RuntimeError)`
- `agent-orchestrator/state.py:9-18` -- `RunState` fields `record_node()` snapshots: `run_id`, `ticket`, `plan`, `file_targets`, `diff`, `test_result`, `review_verdict`, `spend_used`
- `agent-orchestrator/clients/_ssm.py` -- reference pattern: plain `boto3.client(...)` call at point of use, no wrapper class, `RuntimeError` subclass wrapping the underlying exception
- `agent-orchestrator/scripts/provision_secrets_storage.py:164-166` -- confirms bucket naming convention `f"{account_id}-agent-orchestrator-run-logs"` (already provisioned by Story 1.1; this story only writes to it)
- `agent-orchestrator/nodes/implement.py`, `nodes/push.py` -- reference pattern for module docstring style, `RuntimeError`-subclass exceptions, function signatures to mirror
- `agent-orchestrator/tests/test_implement.py`, `tests/test_push.py` -- pattern to mirror: `MagicMock` for `s3_client`, `tmp_path`-independent (no filesystem needed here)

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/run_log.py` -- implement per I/O Matrix -- `RunLog` dataclass, `record_node()`, `finalize()`, `to_json()`, module-level `persist_run_log()` and `RunLogPersistError`
- [x] `agent-orchestrator/tests/test_run_log.py` -- unit tests (mocked `s3_client` via `MagicMock`) covering normal trace accumulation, successful persist (asserting the exact S3 key format and that `put_object`'s body is valid JSON containing all recorded nodes + outcome), failed/aborted persist, S3-failure wrapping, and missing-issue-number rejection

**Acceptance Criteria:**
- Given a Run has completed (successfully, failed, or aborted), when `persist_run_log()` is called, then the full Run Log (every `record_node()` call plus the final outcome) is written to `s3://{run-log-bucket}/runs/{issue-number}/{run-timestamp}/run_log.json`.
- Given the written object, when read back, then it is valid JSON containing each node's captured state and the final outcome, with no dependency on the EC2 instance or any other AWS resource still existing.
- Given an S3 write failure, when `persist_run_log()` is called, then it raises `RunLogPersistError` naming the underlying cause, rather than silently losing the log.

## Design Notes

`record_node()` stores a shallow snapshot of the relevant `RunState` fields (not the whole object via `dataclasses.asdict`, since `ticket` may carry a large GitHub issue body) -- `plan`, `file_targets`, `diff`, `test_result`, `review_verdict`, `spend_used` per node call, so the trace shows how each field evolved across the six nodes without repeating the full ticket body six times.

The S3 key's `{run-timestamp}` segment is generated once, when `persist_run_log()` runs (`datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")`), not per-node -- one log object per Run, not one per node, matching the AC's single `runs/{issue-number}/{run-timestamp}/` path.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_run_log.py -v` -- expected: all pass, no network required (mocked `s3_client`)
- Live smoke test: call `persist_run_log()` against the real provisioned bucket with a throwaway `run_id`/`issue_number` (e.g. `99999`), then `aws s3 ls`/`aws s3 cp` the object back and confirm it parses as JSON -- then delete the throwaway object

## Review Outcome

Three parallel review layers (blind-hunter, edge-case-hunter, verification-gap) all independently flagged `persist_run_log()`'s `except ClientError` as too narrow -- broadened to catch any exception during `to_json()`+`put_object()` so network/credential/serialization failures also become `RunLogPersistError` per the AC's own promise ("raises RunLogPersistError... rather than silently losing the log"). Also patched: failure-path logging, a `finalize()`-was-called precondition, `default=str` safety net in `to_json()`, and a verification-gap-flagged test-coverage hole (snapshot-copy independence for `file_targets`/`test_result` was untested). Full suite: 95/95 passing after patches, no regressions. Live smoke test against the real S3 bucket was not run (no live AWS credentials in this environment) -- covered instead by 9 unit tests. Lower-severity findings (no per-node timestamps, no retry/backoff on the S3 write, no local fallback if S3 persist fails, no `run_id` in the S3 key, no schema version) logged to `deferred-work.md`.

