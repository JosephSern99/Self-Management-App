---
title: 'Story 1.5: Plan & Locate Nodes with Scope Guardrail'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'b83b98582ea061e4c661606957ed8b618b99811e'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing yet turns a Ticket into a concrete, safety-checked list of files to change. The node graph has no Plan or Locate step.

**Approach:** Two node functions taking a `RunState` and returning an updated one: `plan(state, claude_client)` asks Claude to read the issue and write a short change plan; `locate(state, claude_client, repo_dir)` asks Claude to pick concrete file targets grounded in the real tracked-file list (never a hallucinated path), then checks every target against a new `denylist.py` module before allowing the Run to continue.

## Boundaries & Constraints

**Always:** `denylist.py`'s protected-path list is investigated from the real repo, not guessed: `app/Http/Controllers/PaymentController.php`, `app/Http/Controllers/WebhookController.php`, `config/cashier.php`, `database/migrations/**`, `app/Http/Controllers/Auth/**`, `app/Http/Requests/Auth/**`, `app/Http/Middleware/Authenticate.php`, `app/Http/Middleware/RedirectIfAuthenticated.php`, `routes/auth.php`. Locate only ever proposes file targets that exist in `git ls-files` output for the working copy -- a path Claude names that isn't actually tracked in the repo is rejected as a hallucination, not silently accepted. Both nodes call Claude exclusively through `ClaudeClient` (AD-6) -- never a raw SDK call.

**Ask First:** Nothing requires a mid-execution human decision -- a denylist match or hallucinated path aborts the Run automatically per FR-5, it doesn't pause for approval (there is no approval step in this system by design).

**Never:** Do not implement Implement/Test/Self-Review/Push here (Stories 1.6–1.7). Do not wire an `orchestrator.py`/LangGraph `StateGraph` entrypoint yet -- that's deferred until all six nodes exist, so it's built once instead of incrementally reshaped each story. Do not expand the denylist beyond what FR-5/AD-7 name (payments, auth, migrations) -- that would be scope creep on a safety mechanism that should stay exactly as specified.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal ticket | `state.ticket` has a real issue title/body describing a scalability gap | `plan()` returns non-empty `state.plan` text referencing the ticket | N/A |
| Locate proposes only safe files | Plan describes a change to, e.g., `FinanceController` | `locate()` returns `state.file_targets` containing only real, tracked, non-denylisted paths | N/A |
| Locate proposes a denylisted file | Claude (correctly or not) names `app/Http/Controllers/PaymentController.php` as a target | `locate()` raises `ScopeViolation` before returning, naming the offending path and which denylist pattern matched | Run aborts; caller is responsible for recording this in the Run Log (Story 1.8) |
| Locate proposes a path not in the repo | Claude names a plausible-sounding but nonexistent file | `locate()` raises `ScopeViolation` (hallucination is treated the same as a denylist hit: unsafe to proceed) rather than silently including it | N/A |
| Locate proposes zero files | Claude returns an empty file list | `locate()` raises `ScopeViolation` -- an empty target list means nothing to safely implement, not a valid outcome | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/denylist.py` -- new: `is_denylisted(path) -> str | None` (returns the matching pattern, or `None`)
- `agent-orchestrator/nodes/__init__.py` -- new: package marker
- `agent-orchestrator/nodes/plan.py` -- new: `plan(state, claude_client) -> RunState`
- `agent-orchestrator/nodes/locate.py` -- new: `locate(state, claude_client, repo_dir) -> RunState`, imports `denylist`
- `agent-orchestrator/state.py` -- reference only (Story 1.4): `RunState` fields this story populates (`plan`, `file_targets`)
- `agent-orchestrator/clients/claude_client.py` -- reference only (Story 1.4): both nodes call `ClaudeClient.complete()`

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/denylist.py` -- implement `is_denylisted()` against the investigated real paths listed in Boundaries, using glob-style matching so `database/migrations/**` covers the whole directory
- [x] `agent-orchestrator/nodes/plan.py` -- implement `plan()` per I/O Matrix
- [x] `agent-orchestrator/nodes/locate.py` -- implement `locate()` per I/O Matrix -- grounds Claude's file picks against `git ls-files`, validates existence, checks the denylist
- [x] `agent-orchestrator/tests/test_denylist.py` -- unit tests: each named protected path matches, a representative safe path doesn't, `database/migrations/**` glob covers a nested example
- [x] `agent-orchestrator/tests/test_locate.py` -- unit tests (mocked `ClaudeClient`) covering the I/O Matrix's `locate()` rows: denylist hit, hallucinated path, empty list, normal case
- [x] `agent-orchestrator/tests/test_plan.py` -- unit tests (mocked `ClaudeClient`) covering `plan()`, including the null-body prompt-corruption fix

**Acceptance Criteria:**
- Given a started Run for a real Ticket, when `plan()` runs, then it returns a written plan referencing the ticket's content.
- Given a plan describing a safe change, when `locate()` runs, then it returns only real, tracked, non-denylisted file paths.
- Given a plan (or a Claude response) that names a denylisted path, when `locate()` runs, then it raises `ScopeViolation` before any file is returned as approved, naming the path and matching pattern.
- Given `git ls-files` doesn't contain a path Claude proposed, when `locate()` runs, then it raises `ScopeViolation` rather than trusting an unverified path.

## Design Notes

`locate()`'s prompt includes the full `git ls-files` output (the real repo is small enough that this fits comfortably in context) rather than a directory tree summary, so Claude picks from real paths instead of inferring plausible-but-wrong ones. Claude is asked to respond with a JSON array of paths; `locate()` parses and validates it, not just eval'ing a string.

`ScopeViolation` (new exception in `denylist.py`) is the single type both "denylist hit" and "hallucinated path" raise, since Locate's job is "only ever propose files that are both real and in scope" — the caller (future `orchestrator.py`, Story 1.7's wiring) doesn't need to distinguish the two failure reasons to know it must abort the Run.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_denylist.py agent-orchestrator/tests/test_locate.py -v` -- expected: all pass, no network calls
- Small live smoke test: run `plan()` then `locate()` against a real, minor, non-denylisted change description, using the real `ClaudeClient` and the actual cloned repo -- expected: a real plan and a real, sensible file list, no `ScopeViolation`

## Spec Change Log

- 2026-09-02: Review (blind hunter, edge-case hunter, verification-gap, run against a file explicitly called out as the sole safety mechanism before an unreviewed push) found the denylist's own scope and matching logic both had real gaps. Scope: added `config/auth.php`, `config/sanctum.php`, `app/Providers/AuthServiceProvider.php`, `app/Http/Kernel.php`, `bootstrap/app.php`, `app/Models/User.php` (carries the Cashier `Billable` trait), and the four dependency-manifest files (`composer.json`/`.lock`, `package.json`/`-lock.json`) -- all investigated as real, currently-existing paths in the repo, not guessed. Matching: `is_denylisted()` now normalizes case, resolves `../` traversal and repeated slashes, decodes URL-encoding, and strips trailing slashes before comparing, and literal (non-glob) patterns compare with `==` instead of `fnmatch` (which treats `*`/`?`/`[...]` as live wildcards). KEEP: the glob-suffix (`/**`) mechanism for `database/migrations/**` and the Auth-prefixed directories is unchanged and correct.
- 2026-09-02: `locate.py` amended to reject any proposed path that resolves to a symlink on disk (can't verify a symlink's real target is safe), to cap proposed targets at 10 (a scoped single-feature fix shouldn't need more), to use `git ls-files -z` instead of newline-splitting (robust against filenames with special characters), and to log every rejection. `plan.py` amended to fix a real bug: `issue.get('body', '')` returns `None` (not `''`) for a GitHub issue with an explicitly null body, leaking the literal text "None" into every such prompt -- fixed via `or ''`.

## Live Verification

Verified 2026-09-02:
- `python -m pytest agent-orchestrator/tests/ -v` -- 43/43 passed across the full suite (denylist: protected/safe examples, traversal, case-insensitivity, URL-encoding, repeated/trailing slashes; locate: safe/denylisted/hallucinated/empty/oversized/symlinked targets, malformed JSON, markdown-fence stripping, Claude-failure wrapping; plan: normal case, null-body fix, missing-number handling, non-dict ticket, Claude-failure wrapping).
- Live smoke test (`smoke_test_plan_locate.py`) against the real repo and a real Claude call, using the same `FinanceController` scalability gap from the Node Trace mockup: `plan()` produced a genuine, well-scoped plan (missing index on `financial_entities.user_id`); `locate()` correctly identified that the fix requires a new migration and the denylist correctly blocked it (`database/migrations/**`) -- full end-to-end proof the safety mechanism works on a real, non-contrived case. See conversation notes: this also surfaces a real product constraint (index-adding fixes can never pass Locate) worth Joseph's awareness when choosing the actual first Ticket, not a defect in this story.

## Suggested Review Order

**The safety-critical file (start here)**

- Scope: every protected path, each with the investigation note for why it's there.
  [`denylist.py:31`](../../../agent-orchestrator/denylist.py#L31)

- Matching: normalization defends against traversal, case, encoding, and separator bypass attempts.
  [`denylist.py:69`](../../../agent-orchestrator/denylist.py#L69)

**Locate's guardrail enforcement**

- Every proposed path checked against tracked-file membership, denylist, and symlink status -- all-or-nothing.
  [`locate.py:99`](../../../agent-orchestrator/nodes/locate.py#L99)

- Robust tracked-file listing that can't be corrupted by unusual filenames.
  [`locate.py:29`](../../../agent-orchestrator/nodes/locate.py#L29)

**The null-body fix**

- Why `.get(key, default)` doesn't catch an explicit `None` value.
  [`plan.py:18`](../../../agent-orchestrator/nodes/plan.py#L18)
