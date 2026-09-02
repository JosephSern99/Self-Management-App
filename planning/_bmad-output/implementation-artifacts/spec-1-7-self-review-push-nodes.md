---
title: 'Story 1.7: Self-Review & Push Nodes with Final Guardrail Check'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '2ae5671b1e8148ab995d1decd3f2820ba911e6ff'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Test produces a passing `state.diff`, but nothing checks it against the plan/conventions before it ships, and nothing re-verifies the actual changed files are safe before pushing straight to `main` with no human review gate.

**Approach:** `self_review()` asks Claude to compare `state.diff` against `state.plan` and the app's `CLAUDE.md` conventions, writing `PASS`/`FAIL: reason` into `state.review_verdict`; a `FAIL` raises and stops the Run before Push. `push()` re-derives the actual diffed file list from git (not Locate's planned list) and re-checks every path against `denylist.py`; a clean check commits+pushes via `GitHubClient.push()`, then comments a summary on the issue and closes it.

## Boundaries & Constraints

**Always:** Push re-checks paths from the real `git diff --name-only` output in `repo_dir`, never `state.file_targets` — this is the second, independent denylist check required by AD-7/FR5, and it must catch drift Implement's retries may have introduced. A `FAIL` review verdict or any denylist match at Push aborts before any git mutation (no add/commit/push) and before the issue is touched.

**Ask First:** Nothing requires a mid-execution human decision — reject-then-halt is automatic, matching the no-approval-gate design.

**Never:** Do not attempt to auto-fix a `FAIL` verdict or a Push-stage denylist match — either aborts the Run; recovery is Story 1.6's existing Implement retry loop only (already exhausted by the time Self-Review runs), not a new loop here. Do not build `orchestrator.py`/graph-wiring in this story — deferred (see Design Notes); this spec covers only `nodes/self_review.py` and `nodes/push.py` in isolation, called directly like Story 1.5/1.6's nodes are in their own tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Review passes | `state.diff` matches `state.plan`, no convention violations | `state.review_verdict = "PASS"`, state returned | N/A |
| Review fails | Claude judges diff doesn't match plan or violates a `CLAUDE.md` convention | `state.review_verdict` set to `"FAIL: <reason>"` then `SelfReviewRejected` raised | Run halts, Push never runs |
| Push clean | Diffed files (via `git diff --name-only`) are all outside `denylist.py` | `github_client.push()` called, issue commented + closed | N/A |
| Push blocked by drift | A diffed file matches a denylist pattern despite Locate's approval | `ScopeViolation` raised before any add/commit/push | Run halts, issue untouched |
| Nothing to push | `state.diff` is empty (e.g. Implement's diff capture failed silently) | Push raises `ValueError` before calling git | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/nodes/self_review.py` -- new: `self_review(state, claude_client, repo_dir) -> RunState`, `SelfReviewRejected(RuntimeError)`
- `agent-orchestrator/nodes/push.py` -- new: `push(state, github_client, repo_dir) -> RunState`, reuses `denylist.ScopeViolation`
- `agent-orchestrator/state.py:9-18` -- `RunState.diff`, `.plan`, `.review_verdict`, `.ticket` (`{number, title, body}` per test fixtures) consumed here
- `agent-orchestrator/denylist.py:65,76` -- `ScopeViolation`, `is_denylisted(path) -> str | None`; Push imports and calls this per diffed path, same as `locate.py`
- `agent-orchestrator/clients/github_client.py:38-93,95-173` -- `GitHubClient.comment_issue()`, `.close_issue()`, `.push(repo_dir, commit_message, paths=None) -> str` (commit SHA); already fully implemented, Push calls it rather than shelling git itself
- `agent-orchestrator/clients/claude_client.py:35` -- `ClaudeClient.complete(system, messages, max_tokens=4096, node=None) -> str`; Self-Review passes `node="self_review"`
- `agent-orchestrator/nodes/implement.py:117-138` -- reference pattern: node signature shape, `try/except` around Claude calls, `ScopeViolation` usage, module docstring/`SYSTEM_PROMPT` style to mirror exactly
- `agent-orchestrator/nodes/locate.py` -- reference pattern for `is_denylisted()` usage and `logger.warning` before a guardrail raise
- `D:\laragon\www\self-management-app\CLAUDE.md` -- conventions Self-Review checks the diff against (Code style / Service Layer / domain-area table)
- `agent-orchestrator/bootstrap/run.sh:191-195` -- placeholder comment naming this story; NOT wired up here (orchestrator wiring deferred, see Design Notes)
- `agent-orchestrator/tests/test_implement.py`, `test_test_node.py` -- pattern to mirror: `MagicMock` clients, `patch("nodes.push.subprocess.run", ...)`, `tmp_path` as `repo_dir`

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/nodes/self_review.py` -- implement per I/O Matrix -- one Claude call comparing `state.diff` to `state.plan` + `CLAUDE.md` excerpt, parses `PASS`/`FAIL:` prefix, raises `SelfReviewRejected` on fail
- [x] `agent-orchestrator/nodes/push.py` -- implement per I/O Matrix -- `git status --porcelain` in `repo_dir` for the real changed-file list (amended from `git diff --name-only` mid-review to also catch untracked new files -- see below), `is_denylisted()` re-check per file, `state.review_verdict == "PASS"` precondition, `github_client.push()` + `comment_issue()` + `close_issue()` on clean check
- [x] `agent-orchestrator/tests/test_self_review.py` -- unit tests (mocked `ClaudeClient`) covering pass, fail, and malformed-verdict-response edge cases
- [x] `agent-orchestrator/tests/test_push.py` -- unit tests (mocked `GitHubClient`, patched `subprocess.run`) covering clean push (incl. comment-body content), denylist-drift block, empty-diff rejection, untracked-new-file detection, and non-PASS-verdict rejection

**Acceptance Criteria:**
- Given Test has passed, when `self_review()` runs, then it checks `state.diff` against `state.plan` and `CLAUDE.md` conventions and sets `state.review_verdict`.
- Given a `FAIL` verdict, when `self_review()` returns, then `SelfReviewRejected` is raised and the Run does not proceed to Push.
- Given a `PASS` verdict, when `push()` runs, then it re-derives the actual diffed files from git and re-checks each against `denylist.py` independently of Locate's earlier check.
- Given any diffed file matches the denylist, when `push()` runs, then it raises `ScopeViolation` before any git mutation and before the issue is touched.
- Given a clean check, when `push()` completes, then it has committed and pushed directly to `main` via `GitHubClient.push()`, then commented on and closed the GitHub issue with a summary referencing the plan and test outcome.

## Design Notes

`orchestrator.py` (LangGraph `StateGraph` wiring all six nodes, referenced by `bootstrap/run.sh`'s placeholder and Architecture AD-1/spine) does not exist yet in the repo, and `langgraph` isn't in `requirements.txt` — no prior story built it. Wiring it is a distinct goal (new dependency, end-to-end graph construction, spend-cap-at-node-boundary abort logic per AD-8) from "implement these two nodes," so it's out of scope here, matching how Stories 1.5/1.6 shipped nodes without wiring them either. Logged to `deferred-work.md` as the pipeline's actual entrypoint, needed before Story 1.8's "orchestrator finishes its final step" AC is meaningful.

Self-Review's prompt includes the raw `state.diff` and a short excerpt of `CLAUDE.md` (Code style / Service Layer / domain table) rather than the whole file, keeping the call cheap; asks for a first line of exactly `PASS` or `FAIL: <one-sentence reason>` so parsing is a simple prefix check, matching Implement's own "respond with only X" prompting discipline.

Push's git-derived re-derivation (not `state.file_targets`) is the whole point of the AC's "actual diffed files, not just Locate's planned list" — Implement's retries could in principle touch a file not in the original list if Claude's response drifted, so re-deriving from git is the only check that actually closes that gap. Amended mid-review from `git diff --name-only` to `git status --porcelain` — see Spec Change Log.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_self_review.py agent-orchestrator/tests/test_push.py -v` -- expected: all pass, no network/PHP/git-push required (mocked)
- Live smoke test: run `self_review()` + `push()` against a real small non-denylisted change on a throwaway branch/remote (never `origin/main` on the real repo) -- expected: verdict parses correctly, denylist re-check fires on an intentionally-denylisted test file, clean case calls a mocked/dry-run push path

**Manual checks (if no CLI):**
- Confirm no test in `test_push.py` ever invokes a real `git push` against `origin/main` -- `GitHubClient` must be a `MagicMock` in every test, never the real client, given the destructive blast radius of an accidental live push.

## Review Outcome

Three parallel review layers (blind-hunter, edge-case-hunter, verification-gap) all independently converged on `_diffed_files`' `git diff --name-only` missing untracked new files -- patched to `git status --porcelain`, plus added a `state.review_verdict == "PASS"` precondition in `push()` as defense-in-depth (`orchestrator.py` doesn't exist yet to guarantee node call order) and comment-body content assertions in the existing clean-push test. Full suite: 86/86 passing after patches, no regressions. Live smoke test against a real remote/branch was not run (no live GitHub/EC2 credentials in this environment) -- covered instead by 17 unit tests across both new node files. Remaining lower-severity findings (pre-existing `implement.py` diff blind spot for untracked files, missing-issue-number handling, no rollback if push succeeds but comment/close fails, no spend-cap re-check in `push()`, unsanitized commit-message/comment interpolation) logged to `deferred-work.md`.

