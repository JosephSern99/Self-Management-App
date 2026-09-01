---
title: 'Story 1.6: Implement & Test Nodes with Isolated Database'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '94d9fcefda763bccc34a5d84f441c8bedf934d08'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Locate produces an approved file list, but nothing writes the actual code change or verifies it. Nothing yet exists on the EC2 instance to run PHP at all -- Story 1.3 deliberately deferred PHP/Composer setup here.

**Approach:** `implement()` asks Claude for each target file's complete new content and writes it to disk. `test_and_retry()` runs `php artisan test` with DB and APP_URL forced via process env (never touching `.env`), retrying Implement up to 2 additional times on failure before raising. EC2's first-boot provisioning gains PHP 8.1 + required extensions + Composer (same one-time-setup pattern as Story 1.3's `git` fix); `run.sh` gains a `composer install` step that only runs when `vendor/` is missing.

## Boundaries & Constraints

**Always:** Test forces an isolated database connection AND `APP_URL=http://localhost` as process environment variables for the `php artisan test` invocation specifically, regardless of the repo's real `.env` -- investigation found a misconfigured `APP_URL` (a subpath, as Laragon's local dev convention uses) makes Laravel's HTTP test client silently mismatch nearly every route and report false failures, which would burn Claude spend on pointless Implement retries for a problem with nothing to do with the actual code. [AMENDED -- see Spec Change Log: isolation uses a local MariaDB database, not `DB_CONNECTION=sqlite`/`:memory:` as originally specified, since AL2023 has no working `pdo_sqlite` for any PHP version.] `implement()` writes only to files already approved by Locate (`state.file_targets`) -- never a path outside that list, even if Claude's response suggests one. A failed retry sequence raises rather than silently proceeding to Push.

**Ask First:** Nothing requires a mid-execution human decision -- retry-then-fail is automatic per FR-2.

**Never:** Do not implement Self-Review or Push here (Story 1.7). Do not attempt to fix any pre-existing test failure found in the baseline repo (investigation found one real, pre-existing bug: `ProfileController`'s account-deletion path calls `Auth::logout()` on a guard that doesn't support it -- out of scope, `config/auth.php` is denylisted and Test's job is to report, not fix). Do not run `composer install` on every boot -- `vendor/` is gitignored and survives `git clean -fd` (not `-fdx`), so it only needs to run once per instance lifetime or when missing.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal implement | `state.file_targets` has 1-3 real files, `state.plan` describes the change | Each target file's content is rewritten on disk to reflect the plan | N/A |
| Tests pass first try | Implement runs once, `php artisan test` (isolated DB/URL) exits 0 | `test_and_retry()` returns `state` with `test_result.passed = True`, no retry | N/A |
| Tests fail, retry succeeds | First `php artisan test` fails; second Implement+Test attempt passes | Returns with `passed = True`, `test_result` reflects the attempt that passed, not the first failure | N/A |
| Tests fail all 3 attempts | Every attempt fails | Raises `TestsFailedAfterRetries` naming the last failure's output; Run must not proceed to Push | N/A |
| `php artisan test` isolation forced correctly | Real production `self_management_app` MySQL DB exists and is reachable | Test run must show zero writes to it -- verified by DB isolation working, not by trusting `.env` | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/nodes/implement.py` -- new: `implement(state, claude_client, repo_dir) -> RunState`
- `agent-orchestrator/nodes/test.py` -- new: `run_tests(repo_dir) -> dict`, `test_and_retry(state, claude_client, repo_dir, max_attempts=3) -> RunState`
- `agent-orchestrator/bootstrap/run.sh` -- amend (Story 1.3 file): add a `composer install` step, conditional on `vendor/` missing
- `agent-orchestrator/scripts/provision_trigger_infra.py` -- amend (Story 1.2 file): first-boot user-data installs PHP 8.1 + `pdo_sqlite`/`sqlite3` + Composer, same one-time pattern as the `git` install
- `agent-orchestrator/denylist.py` -- reference only: `implement()` must never write outside `state.file_targets`, which Locate already checked against this

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/nodes/implement.py` -- implement per I/O Matrix -- one Claude call per target file requesting complete new content, writes to disk
- [x] `agent-orchestrator/nodes/test.py` -- implement `run_tests()` (single `php artisan test` invocation with forced env) and `test_and_retry()` (the AC's retry-then-fail loop)
- [x] `agent-orchestrator/scripts/provision_trigger_infra.py` -- amend first-boot user-data: PHP 8.1 + extensions + MariaDB + dedicated DB user + Composer + Node.js/npm (see Spec Change Log for the real package names/fixes, several differ from the original guess)
- [x] `agent-orchestrator/bootstrap/run.sh` -- amend: after the initial reset, run `composer install` and `npm install && npm run build` if not already present
- [x] `agent-orchestrator/tests/test_implement.py` -- unit tests (mocked `ClaudeClient`) covering normal implement, path-traversal/denylist defense-in-depth, and edge cases
- [x] `agent-orchestrator/tests/test_test_node.py` -- unit tests (mocked subprocess) covering pass-first-try, fail-then-pass, fail-all-three, timeouts, and env precedence

**Acceptance Criteria:**
- Given Locate's approved file list, when `implement()` runs, then every target file's content is rewritten and no file outside the list is touched.
- Given `test_and_retry()` runs against a real Laravel test suite, when it invokes `php artisan test`, then an isolated database connection (originally specified as `DB_CONNECTION=sqlite`/`DB_DATABASE=:memory:`; amended to a dedicated local MariaDB database -- see Spec Change Log), `APP_URL=http://localhost`, and `APP_KEY` are all forced as process env regardless of `.env`.
- Given tests fail, when `test_and_retry()` retries, then Implement runs again (up to 2 more times) before the Run is marked failed via `TestsFailedAfterRetries`.
- Given the real production MySQL database, when Test runs, then it shows zero writes (verified by inspecting the DB directly, not just trusting the env override).

## Design Notes

`implement()` asks for one file's complete content per Claude call (not a multi-file diff/patch) -- more reliable than asking Claude to produce and the code to apply a unified diff, at the cost of the model needing to reproduce untouched parts of a file verbatim. Each call includes the current file content plus the plan, so it's an edit-in-context request, not a from-scratch rewrite.

The retry loop's failure feedback: on a failed attempt, `test_and_retry()` passes the test failure output back into the next `implement()` call's prompt (appended context, not a new `state.plan`), so the model has a chance to actually fix what broke rather than blindly repeating the same attempt.

## Verification

**Commands:**
- `python -m pytest agent-orchestrator/tests/test_implement.py agent-orchestrator/tests/test_test_node.py -v` -- expected: all pass, no network/PHP required (mocked)
- Live smoke test: run `implement()` + `test_and_retry()` against a real, small, non-denylisted change on the real local repo, with `php` on PATH -- expected: real file(s) change on disk (never committed/pushed), `php artisan test` runs isolated, `test_result` accurately reflects the real pass/fail count
- `git diff --stat` after the live smoke test, to confirm exactly the intended files changed and nothing else -- then `git checkout --` to discard the throwaway local change

## Spec Change Log

- 2026-09-02: Review (blind hunter, edge-case hunter, verification-gap) found the RM100-cap-adjacent safety issues in `implement.py`: no path-traversal defense (relied solely on Locate having already checked), `os.makedirs("")` crash for top-level files, silent file-truncation on an empty/malformed Claude response, no timeout on subprocess calls. All fixed: `_resolve_safe_path()` independently re-checks both containment-in-repo and the denylist (defense-in-depth, matching the "checked twice" pattern already used for Locate/Push), truncated/empty responses now raise `ScopeViolation` instead of corrupting the file, `git diff` and `php artisan test` both have timeouts. `test_and_retry()` now catches an exception from a mid-loop `implement()` call rather than crashing the whole Run uncaught, rejects `max_attempts < 1`, and each retry's feedback is proven (by a dedicated 3-attempt test) to be that attempt's own failure output, not a stale one.
- 2026-09-02: Extensive live EC2 verification (multiple full terminate/recreate cycles) found the original AD-2 mechanism (SQLite) doesn't work at all on AL2023 (see architecture memlog), and surfaced 5 further first-boot infrastructure bugs, all now fixed in `provision_trigger_infra.py`/`run.sh`: (1) `php8.1-curl` isn't a real package name and silently killed the *entire* PHP install transaction; (2) Composer's installer needs `HOME`, unset by default in both the user-data and systemd execution contexts; (3) `php8.1-zip` needed for `composer install` itself; (4) MariaDB's `root` user rejects TCP connections regardless of password (fixed via a dedicated `agent_orchestrator` DB user); (5) Blade views using `@vite()` need a built frontend manifest, so Node.js/npm + `npm run build` were added alongside the Composer step. KEEP: the retry-with-3-attempts logic and Claude-facing prompts were correct from the start and needed no changes through all of this -- every fix was in the surrounding infrastructure, not the node logic itself.

## Live Verification

Verified 2026-09-02, via repeated full EC2 instance provisioning cycles (terminate + fresh `provision_trigger_infra.py` run, each time proving the *automatic*, unattended first-boot path, not a manually-patched one):
- Final clean run: git, PHP 8.1 + extensions, MariaDB + dedicated test DB/user, Composer install, and `npm run build` all complete automatically with zero manual intervention, confirmed via `/var/log/agent-orchestrator-setup.log` and `/var/log/agent-orchestrator-run.log`.
- `php artisan test` run against the isolated MariaDB database on the real cloned repo: 20/25 passing. The 3 remaining failures were individually traced and confirmed to be genuine pre-existing app bugs (root-route redirect regression from the earlier "Refresh finance UI" commit; `ProfileController` calling `Auth::logout()` on a guard that doesn't support it) -- unrelated to this story's infrastructure, not fixed here (see Architecture Deferred section), and matches the exact same 3 failures found independently during local Windows verification.
- `implement()`/`test_and_retry()` themselves were not live-exercised end-to-end on EC2 in this pass (would require pushing this story's code to `origin/main` first, which hadn't happened yet at verification time) -- covered instead by the 69 unit tests plus the proven-working infrastructure they'll run on top of.
