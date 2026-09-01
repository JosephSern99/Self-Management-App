# Epic 1 Context: Autonomous Ticket Resolution

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Joseph files a GitHub Issue describing a scalability/maintainability gap in `self-management-app`; the system detects it, runs a fully autonomous six-node agent pipeline (Plan, Locate, Implement, Test, Self-Review, Push), and lands a working fix directly on `main` — zero lines of code written by Joseph, with no human approval gate at any step. The primary risk mitigation for pushing straight to `main` on a live app that processes Stripe payments is a denylist guardrail rather than human review, so guardrail correctness matters as much as the happy path.

## Stories

- Story 1.1: Secrets & Storage Scaffolding
- Story 1.2: Trigger Lambda — Ticket Detection
- Story 1.3: Orchestrator Bootstrap & Clean Working Copy
- Story 1.4: RunState, Client Wrappers & Spend Ledger
- Story 1.5: Plan & Locate Nodes with Scope Guardrail
- Story 1.6: Implement & Test Nodes with Isolated Database
- Story 1.7: Self-Review & Push Nodes with Final Guardrail Check
- Story 1.8: Run Log Persistence to S3

## Requirements & Constraints

- A Ticket is a GitHub Issue labeled `agent-ready` on `self-management-app` describing a single existing feature's scalability/maintainability gap — not new functionality, not a bug fix. Detection must start exactly one Run within ~5 minutes, with no duplicate concurrent Runs per issue.
- The six nodes run in strict order with no human approval gate. A completed Run commits to `main` and closes/comments the issue with a summary. A failed Test retries Implement up to 2 additional times before the Run is marked failed and Push is skipped.
- Cumulative Claude API token spend is tracked against a hard Spend Cap (RM100 for the first trial). No new Run starts once spend is at or above the cap; a Run that would cross the cap mid-execution aborts at the next node boundary, never mid-node.
- All AWS compute/storage must stay within free-tier-safe limits (on-demand EC2, perpetually-free Lambda invocations, S3, SSM) so AWS cost is $0 at v1 usage volumes. No always-on/idle resource is acceptable.
- The agent must never modify payment/Stripe code (`PaymentController`, `WebhookController`, Cashier config), authentication code, or database migrations. This is enforced by a denylist checked twice — once at Locate (planned scope) and again at Push (actual diffed files) — since there is no human review step as a backstop. A match at either check aborts the Run without pushing, with the reason recorded in the Run Log.
- Test execution must never touch the production `self_management_app` MySQL database.
- Success criteria: the one identified feature gap lands on `main` with zero lines written by Joseph; total spend stays at or under RM100; the agent must not "succeed" by weakening/skipping tests or touching files outside Locate's identified scope.

## Technical Decisions

- Architecture paradigm: pipes-and-filters DAG via a single LangGraph `StateGraph`. One Python orchestrator process per Run. Each node is a pure function `RunState -> partial RunState`; only Implement is allowed to write files to the working copy directly.
- Single shared `RunState` object with fixed field names: `ticket`, `plan`, `file_targets`, `diff`, `test_result`, `review_verdict`, `spend_used`, `run_id`. Nodes must not otherwise touch filesystem/network/AWS APIs directly.
- Exactly one `GitHubClient` (issue read/comment/close, git push) and one `ClaudeClient` (all LLM calls) — nodes never call raw `PyGithub`/`anthropic` SDKs. `ClaudeClient` logs token usage to `SpendLedger` on every call before returning.
- `denylist.py` is the single source of truth for protected paths (`PaymentController.php`, `WebhookController.php`, Cashier/Stripe config, `database/migrations/**`, auth controllers/middleware), imported by both `nodes/locate.py` and `nodes/push.py`.
- `SpendLedger` is a single append-only JSON file on the EC2 instance's persistent disk, summed at orchestrator startup and before allowing any new Run.
- Test node forces `DB_CONNECTION=sqlite` / `DB_DATABASE=:memory:` as process env overrides for `php artisan test`, regardless of the repo's real `.env` (which defaults to MySQL with no test override committed).
- One persistent git working copy on the EC2 instance. Orchestrator runs `git fetch && git reset --hard origin/main` before Plan starts and again after the Run ends (success, failure, or abort) — never left dirty.
- EC2 (t3.micro) is on-demand: started only by the Trigger Lambda per matching Ticket, and stopped by the orchestrator as the last action of every Run.
- Trigger is an EventBridge-scheduled Lambda (every 5 minutes) polling the GitHub Issues API for `agent-ready` labels — not a webhook, to avoid needing a public HTTPS endpoint.
- Secrets (GitHub PAT, Claude API key) are stored as SSM Parameter Store `SecureString` standard parameters (not Secrets Manager, to avoid cost), read once at orchestrator startup. No credential in plaintext on disk or in a Lambda/EC2 env variable.
- Run Log (plan, diffs, test output, per-node trace, final outcome) is written to `s3://{run-log-bucket}/runs/{issue-number}/{run-timestamp}/`, readable without the EC2 instance existing.
- Project layout: `agent-orchestrator/orchestrator.py`, `state.py`, `nodes/{plan,locate,implement,test,self_review,push}.py`, `clients/{github_client,claude_client}.py`, `denylist.py`, `spend_ledger.py`, `trigger_lambda/handler.py`.
- Stack: Python 3.12, LangGraph 1.2.x, anthropic SDK 1.1.x, boto3, PyGithub; inherited unchanged: PHP ^8.1, Laravel ^10.10, phpunit ^10.1.
- This is a brand-new Python/AWS subsystem alongside the existing Laravel app — nothing here modifies existing `self-management-app` PHP code except what a Run itself produces as its change.

## Cross-Story Dependencies

- Story 1.2 (Trigger Lambda) depends on Story 1.1 (secrets/S3 must exist first) and starts the EC2 instance that Story 1.3 bootstraps.
- Story 1.3 (bootstrap/clean working copy) must run before any node executes and must wrap every Run's start/end, so it effectively wraps Stories 1.5–1.7.
- Story 1.4 (RunState, client wrappers, SpendLedger) is a foundation all of Stories 1.5–1.7 depend on — nodes cannot be implemented without the shared `RunState` contract and the two client wrappers.
- Story 1.5's Locate denylist check and Story 1.7's Push denylist check both import the same `denylist.py` (Story 1.5 introduces it; Story 1.7 reuses it) — they must stay in sync, not maintain separate lists.
- Story 1.6 (Implement/Test) depends on Story 1.5 having produced an approved file list from Locate; a Test failure loops back to Implement (up to 2 retries) within Story 1.6 before the Run can proceed to Story 1.7.
- Story 1.8 (Run Log to S3) depends on every other story's nodes appending their input/output to the Run Log object during the Run; it is the final step regardless of Run outcome (success, failure, or abort) and depends on Story 1.1's S3 bucket.
