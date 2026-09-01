---
title: Claude Agentic Graph Engineering Node Workflow
status: final
created: 2026-09-01
updated: 2026-09-01
---

# PRD: Claude Agentic Graph Engineering Node Workflow
*Working title — confirm.*

## 0. Document Purpose
This PRD scopes a personal-infra tool for Joseph: an autonomous, LangGraph-style agent pipeline that takes a single GitHub Issue on the `self-management-app` repo and ships a working improvement — end to end, no human in the loop, zero lines of code written by Joseph. It is written for Joseph as sole builder and sole reader; downstream, it hands off to `bmad-architecture` for the node-graph technical design. Assumptions inferred without confirmation are tagged `[ASSUMPTION]` and indexed in §9.

## 1. Vision
Joseph maintains `self-management-app`, a Laravel personal finance app, largely solo. Today, improving it means Joseph reading the code, writing the fix, testing it, and shipping it himself. This product replaces that loop for well-scoped tickets: Joseph files a GitHub Issue describing a gap, and a graph of Claude-powered agent nodes — plan, code, test, review, push — runs unattended and lands the change on `main`.

The system is deliberately minimal for v1: one ticket, one pass, one small feature-scale fix, proving the loop works before it's trusted with more. It matters because it turns "I noticed this code doesn't scale" into a self-resolving signal instead of a backlog item competing for Joseph's own time.

## 2. Target User

### 2.1 Jobs To Be Done
- As the sole maintainer of `self-management-app`, I want to file an issue and have it resolved without touching an editor, so my own time isn't the bottleneck on small maintainability fixes.
- I want to validate, cheaply (≤RM100 in Claude spend), whether an autonomous coding agent can be trusted with real changes to my app before I extend it further.

### 2.2 Non-Users (v1)
- Not built for a team — no multi-user ticket queue, no reviewer role, no notification/chat integration beyond GitHub itself.
- Not built for arbitrary repos in v1 — scoped to `self-management-app` only.

### 2.3 Key User Journeys
**Lighter scope (hobby/solo tool) — single-sentence form:**

- **UJ-1.** Joseph, wanting a specific known-weak feature improved without writing code himself, files a GitHub Issue describing the gap; the agent graph picks it up, plans, implements, tests, and pushes the fix to `main` unattended, and Joseph comes back to a closed issue and a green build.

## 3. Glossary
- **Ticket** — A GitHub Issue on `self-management-app` that describes one feature gap (scalability or maintainability) for the agent to resolve. One ticket = one run.
- **Run** — A single end-to-end execution of the Node Graph against one Ticket, from pickup to push (or failure).
- **Node Graph** — The LangGraph-style DAG of agent steps that constitutes a Run. See FR-2 for node list.
- **Node** — One step in the Node Graph (e.g., Planner, Coder, Tester). Each Node is a Claude API call (or sequence of calls) with a defined input/output contract.
- **Trigger** — The mechanism that starts a Run when a Ticket is filed or labeled. [ASSUMPTION: GitHub webhook or polling — see FR-1.]
- **Run Log** — The persisted record of what a Run did: plan, diffs, test results, decisions, final outcome.
- **Spend Cap** — The hard ceiling (RM100 for the first trial) on Claude API token spend across Run(s).

## 4. Features

### 4.1 Ticket Intake & Trigger
**Description:** Joseph files a GitHub Issue on `self-management-app` describing one feature with a scalability/maintainability gap. The system detects the new/labeled issue and starts a Run. Realizes UJ-1.

**Functional Requirements:**

#### FR-1: Detect a new Ticket and start a Run
The system can detect a new GitHub Issue (or an issue with a specific label, e.g. `agent-ready`) on `self-management-app` and start exactly one Run for it. [ASSUMPTION: trigger is a label-gated poll or webhook from GitHub to a Lambda; polling chosen by default for free-tier simplicity unless Joseph prefers a webhook.]

**Consequences (testable):**
- An issue labeled `agent-ready` results in a Run starting within [ASSUMPTION: 5 minutes] without manual action.
- An issue without the label does not trigger a Run.
- Only one Run is active per Ticket at a time (no duplicate concurrent Runs on the same issue).

**Out of Scope:**
- Ticket authoring/templating UI — Joseph writes the issue body freely.

### 4.2 Node Graph Execution
**Description:** The core LangGraph-style DAG that turns a Ticket into a shipped change: Plan → Locate → Implement → Test → Self-Review → Push. Fully autonomous — no approval gate at any node. Realizes UJ-1.

**Functional Requirements:**

#### FR-2: Execute the full node graph without human approval
Given a started Run, the system executes, in order: (1) **Plan** — reads the issue, produces a change plan; (2) **Locate** — identifies the relevant files in the Laravel app; (3) **Implement** — writes the code change; (4) **Test** — runs `php artisan test` (and any feature-relevant checks) against the change; (5) **Self-Review** — a Claude pass checking the diff against the plan and repo conventions (per `CLAUDE.md`); (6) **Push** — commits and pushes directly to `main`. No node pauses for Joseph's approval.

**Consequences (testable):**
- A Run that completes all six nodes successfully results in a commit on `main` and the GitHub Issue closed/commented with a summary.
- If Test fails, the Run does not proceed to Push; it retries Implement up to [ASSUMPTION: 2] times before marking the Run failed.
- Every Run produces a Run Log capturing each node's output, retained for Joseph to inspect after the fact even though no approval was required during the Run.

**Out of Scope:**
- Any interactive approval/pause step — explicitly excluded per Joseph's direction (push straight to main, fully autonomous).

**Notes:**
- `[NOTE FOR PM]` Pushing directly to `main` on a live app that processes Stripe payments (MYR) carries real blast-radius risk if a Run produces a subtly broken change that passes its own tests. Joseph confirmed this is the intended v1 behavior; flagged here for revisit once more than one Ticket has run successfully. See FR-4 for the guardrail that scopes *what* the agent may touch as the primary risk mitigation instead of a human gate.

### 4.3 Cost & Spend Control
**Description:** Keeps AWS cost near zero and hard-caps Claude API spend for the first trial. Realizes UJ-1 (job: validate cheaply before trusting the system further).

**Functional Requirements:**

#### FR-3: Enforce a hard Claude API spend cap
The system tracks cumulative Claude API token spend across Run(s) against a configured Spend Cap (RM100 / ~USD21 for the first trial) and halts further Runs once the cap is reached.

**Consequences (testable):**
- No new Run starts once tracked spend is at or above the Spend Cap.
- A Run that would exceed the cap mid-execution is aborted at the next node boundary rather than continuing unbounded.
- Joseph can see cumulative spend-to-date via the Run Log or a simple summary. [ASSUMPTION: spend estimated from Claude API token usage per call, logged per Run, summed — not a live billing API integration.]

#### FR-4: Run entirely on AWS free-tier infrastructure
The system's compute/storage (trigger listener, orchestration runtime, Run Log storage) runs within AWS free-tier limits, so AWS cost is $0 for v1 usage volumes.

**Consequences (testable):**
- Infra choices are limited to free-tier-eligible services (e.g., Lambda within free monthly invocations, S3 within free storage tier). [ASSUMPTION: exact service list decided at architecture stage — this FR fixes the cost constraint, not the specific services.]
- No AWS resource is provisioned that carries a non-trivial baseline cost (e.g., an always-on EC2 instance, a provisioned-capacity database).

### 4.4 Change Scope Guardrail
**Description:** Bounds what the agent is allowed to touch, since there is no human approval gate (§4.2). This is the primary safety mechanism for a system that pushes straight to `main` on a live finance app.

**Functional Requirements:**

#### FR-5: Restrict Ticket scope to non-critical maintainability/scalability fixes
For v1, a Ticket must describe a single existing feature with an identified scalability or maintainability gap (not new functionality, not a bug in production behavior). The agent does not modify payment/Stripe code (`PaymentController`, `WebhookController`, Cashier-related config), authentication, or database migrations. [ASSUMPTION: enforced by instruction to the agent plus a Locate-node check that fails the Run if the identified files fall in a denylist, since there is no human review step to catch it otherwise.]

**Consequences (testable):**
- A Run whose Implement/Locate step touches a denylisted path (payments, auth, migrations) is aborted before Push, with the Run Log recording why.
- The denylist check runs twice: once at Locate (planned scope) and again immediately before Push (actual diff'd files) — a Run cannot reach Push solely because Locate missed a path that Implement later touched.
- The one v1 Ticket Joseph plans to file targets a non-payment, non-auth feature.

**Out of Scope:**
- General bug fixes or new-feature Tickets — deferred until the scoped-improvement loop is proven (§6.2).

## 5. Non-Goals (Explicit)
- Not a multi-repo or multi-tenant platform — one repo (`self-management-app`), one Ticket at a time, in v1.
- Not a PR-review workflow — no draft PRs, no review gate; changes land on `main` directly per Joseph's decision.
- Not a general-purpose coding agent product — scoped to this app's maintenance, not a tool Joseph intends to package or sell (unless a future PRD says otherwise).
- Not a monitoring/alerting product — Run Log is for after-the-fact inspection, not real-time paging.

## 6. MVP Scope

### 6.1 In Scope
- GitHub Issue trigger (label-gated) on `self-management-app`.
- Six-node LangGraph-style DAG: Plan, Locate, Implement, Test, Self-Review, Push.
- Direct push to `main` on success; Run aborts (no push) on test failure after retries or on denylisted-path violation.
- Spend Cap enforcement at RM100 for the first trial.
- AWS free-tier-only infrastructure.
- One real Ticket: the scalability/maintainability gap Joseph has already identified.

### 6.2 Out of Scope for MVP
- Human approval/PR-review step — deferred; revisit after v1 proves reliable (see `[NOTE FOR PM]` in §4.2).
- Multiple concurrent Tickets/Runs.
- Tickets that add new features or fix production bugs — v1 is scoped-improvement only (FR-5).
- Any repo other than `self-management-app`.
- Rollback/revert automation if a pushed change turns out to be bad — v1 has no automated undo; Joseph reverts manually if needed. `[NOTE FOR PM]` worth adding once the loop is trusted with more Tickets.

## 7. Success Metrics

**Primary**
- **SM-1**: The one identified feature gap is resolved and pushed to `main` with zero lines of code written by Joseph. Validates FR-2.

**Secondary**
- **SM-2**: Total Claude API spend for the trial stays at or under RM100. Validates FR-3.
- **SM-3**: Time from filing the Ticket to a landed, passing change is small enough that Joseph would trust filing a second Ticket. [ASSUMPTION: no hard number set — Joseph's subjective call after the first Run.]

**Counter-metrics (do not optimize)**
- **SM-C1**: The agent should not "succeed" by weakening or skipping tests to make Test pass — a Run that reports success but reduced test coverage/strictness is a failure, not a win. Counterbalances SM-1.
- **SM-C2**: The agent should not touch files outside the Locate-node's identified scope just to make tests pass faster. Counterbalances SM-1 and FR-5.

## 8. Open Questions
1. Exact Trigger mechanism — GitHub webhook to a public Lambda endpoint, vs. a scheduled poll — needs an AWS-architecture decision (leans free-tier-simpler = poll, per `[ASSUMPTION]` in FR-1).
2. What counts as "test passing" beyond `php artisan test` — is a manual/browser smoke-check ever required, given no human reviews the diff before push?
3. What happens to a Ticket that the Planner deems out of scope (e.g., secretly needs a migration)? v1 assumes the Run just aborts and reports back on the issue — confirm.
4. Retention/format of the Run Log — flat file in S3, DB table, or GitHub issue comments? Left to architecture stage.
5. After the first successful Ticket, does Joseph want to raise the Spend Cap, add more Tickets, or pause and add the human-approval gate deferred in §6.2?

## 9. Assumptions Index
- §3 — Trigger mechanism assumed to be webhook or polling; default leans polling for free-tier simplicity.
- §4.1 (FR-1) — Detection latency assumed ~5 minutes; label used is `agent-ready`.
- §4.2 (FR-2) — Failed Test retries Implement up to 2 times before the Run is marked failed.
- §4.3 (FR-3) — Spend tracked by summing per-call token usage logged per Run, not a live AWS/Anthropic billing API integration.
- §4.3 (FR-4) — Specific AWS free-tier services left to the architecture stage; this PRD only fixes the "must stay free-tier" constraint.
- §4.4 (FR-5) — Denylist enforcement assumed to be a Locate-node path check plus agent instruction, since there is no human review step as a backstop.
- §7 (SM-3) — No hard time target set; success judged subjectively by Joseph after the first Run.
