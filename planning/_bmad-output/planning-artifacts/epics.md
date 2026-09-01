---
stepsCompleted: [step-01, step-02, step-03, step-04]
inputDocuments: ['_bmad-output/planning-artifacts/prds/prd-planning-2026-09-01/prd.md', '_bmad-output/planning-artifacts/architecture/architecture-planning-2026-09-01/ARCHITECTURE-SPINE.md']
---

# Claude Agentic Graph Engineering Node Workflow - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown, decomposing the requirements from the PRD and Architecture Spine into implementable stories. No UX design contract exists for this run (backend/infra tool, no UI).

## Requirements Inventory

### Functional Requirements

FR1: The system can detect a new GitHub Issue labeled `agent-ready` on `self-management-app` and start exactly one Run for it, within ~5 minutes, with no duplicate concurrent Runs per issue.

FR2: Given a started Run, the system executes six nodes in order — Plan, Locate, Implement, Test, Self-Review, Push — fully autonomously with no human approval gate. A completed Run commits to `main` and closes/comments the issue. A failed Test retries Implement up to 2 times before the Run is marked failed. Every Run produces a Run Log.

FR3: The system tracks cumulative Claude API token spend against a Spend Cap (RM100 for the first trial) and halts new Runs once the cap is reached; a Run that would exceed the cap mid-execution aborts at the next node boundary.

FR4: The system's compute/storage runs within AWS free-tier-safe limits (on-demand EC2, perpetually-free Lambda, S3, SSM) so AWS cost stays at $0 for v1 usage volumes.

FR5: A Ticket must describe a single existing feature's scalability/maintainability gap (not new functionality, not a bug fix). The agent must not modify payment/Stripe code, authentication, or database migrations — enforced by a denylist checked at both Locate and Push.

### NonFunctional Requirements

No requirements were labeled NFR in the PRD; the following constraints carry NFR weight and are folded into FR3/FR4/FR5 above rather than duplicated:
- Cost ceiling: RM100 Claude spend (FR3), $0 AWS spend (FR4).
- Safety/blast-radius: denylist enforcement is the sole substitute for a human review gate (FR5).
- Data safety: test execution must never touch the production `self_management_app` MySQL database (Architecture AD-2).

### Additional Requirements

- No starter template — brownfield: builds against the existing `self-management-app` Laravel repo unchanged. (Architecture Stack)
- Infrastructure: on-demand EC2 t3.micro (starts per Run, self-stops after), EventBridge-scheduled Lambda for the 5-minute trigger poll, S3 bucket for Run Log persistence, SSM Parameter Store (SecureString) for GitHub PAT + Claude API key. (AD-3, AD-4, AD-9, AD-10)
- Single persistent git working copy on the EC2 instance, hard-reset to `origin/main` before every Run and after every Run ends (success, failure, or abort). (AD-5)
- Single `RunState` object with fixed field names (`ticket`, `plan`, `file_targets`, `diff`, `test_result`, `review_verdict`, `spend_used`, `run_id`) threading all node I/O. (AD-1)
- Exactly one `GitHubClient` and one `ClaudeClient` wrapper — nodes never call raw SDKs directly; `ClaudeClient` logs every call to `SpendLedger`. (AD-6)
- `denylist.py` is the single source of truth for protected paths, imported by both Locate and Push. (AD-7)
- `SpendLedger` is a single append-only JSON file on the instance's persistent disk, summed before allowing any new Run. (AD-8)
- Test node forces `DB_CONNECTION=sqlite` / `DB_DATABASE=:memory:` as process env overrides for `php artisan test`, regardless of the repo's real `.env`. (AD-2)

### UX Design Requirements

None — no UX design contract exists for this run; this is a backend/infra automation tool with no user-facing UI.

### FR Coverage Map

FR1: Epic 1 - Ticket detection/trigger (Lambda poll)
FR2: Epic 1 - Six-node autonomous execution to a landed commit
FR3: Epic 1 - Spend Cap enforcement
FR4: Epic 1 - Free-tier-safe AWS infrastructure
FR5: Epic 1 - Denylist safety guardrail

## Epic List

### Epic 1: Autonomous Ticket Resolution
Joseph files a GitHub Issue describing a scalability/maintainability gap; the system detects it, runs the full node graph unattended within cost and safety limits, and lands a working fix on `main` — zero lines of code written by Joseph.
**FRs covered:** FR1, FR2, FR3, FR4, FR5

## Epic 1: Autonomous Ticket Resolution

Joseph files a GitHub Issue describing a scalability/maintainability gap; the system detects it, runs the full node graph unattended within cost and safety limits, and lands a working fix on `main` — zero lines of code written by Joseph.

### Story 1.1: Secrets & Storage Scaffolding

As Joseph,
I want the GitHub PAT, Claude API key, and a Run Log bucket provisioned securely on AWS,
So that every later story has a safe place to read credentials from and write audit trails to.

**Acceptance Criteria:**

**Given** an AWS account,
**When** the scaffolding script runs,
**Then** the GitHub PAT and Claude API key exist as SSM `SecureString` standard parameters (not Secrets Manager), and an S3 bucket exists for Run Logs.
**And** no credential is stored in plaintext on disk or in a Lambda/EC2 environment variable.

*Realizes: FR4, AD-9, AD-10*

### Story 1.2: Trigger Lambda — Ticket Detection

As Joseph,
I want a Lambda that polls GitHub every 5 minutes for issues labeled `agent-ready`,
So that filing a Ticket is enough to start a Run without me doing anything else.

**Acceptance Criteria:**

**Given** an open GitHub issue on `self-management-app` labeled `agent-ready` with no Run yet started for it,
**When** the EventBridge-scheduled Lambda next fires,
**Then** it detects the issue and starts the EC2 orchestrator instance, passing the issue number in.
**And** an issue without the label does not trigger a start.
**And** an issue that already has an active Run does not trigger a second, concurrent start.

*Realizes: FR1, AD-3, AD-4*

### Story 1.3: Orchestrator Bootstrap & Clean Working Copy

As Joseph,
I want the EC2 orchestrator to always start from a clean, up-to-date copy of the repo and stop itself when done,
So that no Run is ever contaminated by a previous Run's leftover state, and the instance never idles.

**Acceptance Criteria:**

**Given** the EC2 instance has just started for a given issue number,
**When** the orchestrator boots,
**Then** it runs `git fetch && git reset --hard origin/main` on its persistent working copy before any node runs.
**And** when the Run ends for any reason (success, failure, or abort), the orchestrator repeats the reset and then stops its own EC2 instance.

*Realizes: FR2 (Run lifecycle), AD-3, AD-5*

### Story 1.4: RunState, Client Wrappers & Spend Ledger

As Joseph,
I want one shared RunState object, one GitHubClient, one ClaudeClient, and a SpendLedger enforcing the RM100 cap,
So that every node talks to GitHub/Claude the same way, spend is tracked centrally, and no Run can start once the cap is hit.

**Acceptance Criteria:**

**Given** the orchestrator is about to start a Run,
**When** it checks the SpendLedger,
**Then** it refuses to start if cumulative logged spend is at or above RM100.
**And** every Claude API call made during the Run goes through the single ClaudeClient, which logs token usage to the SpendLedger before returning.
**And** a Run that would cross the cap mid-execution is aborted at the next node boundary rather than mid-node.

*Realizes: FR3, AD-1, AD-6, AD-8*

### Story 1.5: Plan & Locate Nodes with Scope Guardrail

As Joseph,
I want the Plan node to read the issue and produce a change plan, and the Locate node to identify target files and reject anything in the denylist,
So that the system never even attempts to touch payment, auth, or migration code.

**Acceptance Criteria:**

**Given** a started Run for a Ticket describing a scalability/maintainability gap,
**When** Plan and Locate execute,
**Then** Plan produces a written change plan referencing the Ticket, and Locate produces a concrete file list.
**And** if any planned file target matches `denylist.py` (payment/Stripe controllers, Cashier config, `database/migrations/**`, auth), the Run aborts before Implement runs, with the reason recorded in the Run Log.

*Realizes: FR5 (Locate check), AD-7*

### Story 1.6: Implement & Test Nodes with Isolated Database

As Joseph,
I want the Implement node to write the code change and the Test node to verify it against an isolated database,
So that a Run either produces a verified-passing change or fails safely, without ever touching production data.

**Acceptance Criteria:**

**Given** Locate has produced an approved file list,
**When** Implement writes a change and Test runs `php artisan test`,
**Then** Test forces `DB_CONNECTION=sqlite` / `DB_DATABASE=:memory:` regardless of the repo's real `.env`.
**And** if tests fail, Implement is retried up to 2 additional times before the Run is marked failed and does not proceed to Push.
**And** the production `self_management_app` MySQL database shows no writes from the Test node.

*Realizes: FR2 (Test/retry), AD-2*

### Story 1.7: Self-Review & Push Nodes with Final Guardrail Check

As Joseph,
I want the Self-Review node to check the diff against repo conventions, and Push to re-check the denylist before committing straight to `main`,
So that a passing Run actually lands — and a Run that drifted into a denylisted file mid-Implement still can't ship.

**Acceptance Criteria:**

**Given** Test has passed for a Run,
**When** Self-Review and Push execute,
**Then** Self-Review checks the diff against the plan and `CLAUDE.md` conventions.
**And** Push re-checks the actual diffed files against `denylist.py` (not just Locate's planned list) and aborts without pushing if any match.
**And** on a clean check, Push commits and pushes directly to `main`, then comments on and closes the GitHub issue with a summary.

*Realizes: FR2 (Push), FR5 (Push check), AD-7*

### Story 1.8: Run Log Persistence to S3

As Joseph,
I want every Run's full log (plan, diffs, test output, per-node trace, outcome) mirrored to S3,
So that I can inspect what an autonomous Run did after the fact, even after the on-demand EC2 instance is gone.

**Acceptance Criteria:**

**Given** a Run has completed (successfully, failed, or aborted),
**When** the orchestrator finishes its final step,
**Then** the full Run Log is written to `s3://{run-log-bucket}/runs/{issue-number}/{run-timestamp}/`.
**And** the log includes each node's output and the final outcome, readable without needing the EC2 instance to still exist.

*Realizes: FR2 (Run Log), AD-9*
