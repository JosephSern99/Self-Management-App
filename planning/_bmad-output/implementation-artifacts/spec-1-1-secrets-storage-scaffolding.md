---
title: 'Story 1.1: Secrets & Storage Scaffolding'
type: 'feature'
created: '2026-09-01'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '29fb3747e8dc9008c7e142cdc26e4d6671d4f142'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The agent orchestrator (built across Stories 1.2–1.8) needs a GitHub PAT and a Claude API key at runtime, and a durable place to write Run Logs — but nothing on AWS exists yet, and credentials must never live in plaintext on disk or in an environment variable.

**Approach:** A one-time, idempotent boto3 provisioning script that creates two SSM Parameter Store `SecureString` standard parameters (GitHub PAT, Claude API key) and one private S3 bucket for Run Logs, reading the secret values from the operator's environment/prompt rather than hardcoding them.

## Boundaries & Constraints

**Always:** Secrets are SSM `SecureString` standard-tier parameters, never Secrets Manager (cost) and never a plaintext file/env var at rest. The S3 bucket blocks all public access and enforces TLS-only access. The script is idempotent — re-running it must not fail or duplicate resources. Region and bucket naming must not collide with anything else in the account (derive bucket name from the AWS account id).

**Ask First:** Nothing in this story requires a human decision mid-execution beyond supplying the two secret values and running the script themselves (the agent cannot run `aws` commands against a real account without the human's configured credentials).

**Never:** Do not create any EC2, Lambda, or IAM role/policy resources in this story — those belong to Stories 1.2/1.3 when the compute that needs them exists. Do not commit the actual secret values anywhere in the repo.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First run | No SSM params, no bucket exist; `GITHUB_PAT` and `CLAUDE_API_KEY` env vars set | Both SSM `SecureString` params created; S3 bucket created with public access blocked and TLS-only policy | N/A |
| Re-run (idempotency) | Params and bucket already exist from a prior run | Script detects existing resources, updates SSM param values if changed, leaves bucket as-is, exits 0 | N/A |
| Missing secret env vars | `GITHUB_PAT` or `CLAUDE_API_KEY` not set and not supplied interactively | Script prompts via `getpass` for the missing value; never accepts it as a CLI argument | If prompt is also empty, script exits non-zero with a clear message, creates nothing |
| No AWS credentials configured | `aws sts get-caller-identity` fails | Script exits non-zero immediately with a clear message pointing to `aws configure` | Script must not partially create resources before this check |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/scripts/provision_secrets_storage.py` -- new: the provisioning script itself (SSM params + S3 bucket)
- `agent-orchestrator/scripts/__init__.py`, `agent-orchestrator/__init__.py` -- new: empty package markers so later stories can import shared modules
- `agent-orchestrator/requirements.txt` -- new: pins `boto3` for this and all later stories in the epic
- `agent-orchestrator/README.md` -- new: brief operator instructions (env vars needed, how to run the script)

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/requirements.txt` -- add `boto3>=1.34` -- shared dependency for all Story 1.x AWS interactions
- [x] `agent-orchestrator/scripts/provision_secrets_storage.py` -- implement the provisioning script per Boundaries & I/O Matrix above -- creates the two SSM params and the S3 bucket, idempotently, with credential/env checks up front
- [x] `agent-orchestrator/README.md` -- document required env vars (`GITHUB_PAT`, `CLAUDE_API_KEY`) and how to run the script -- so Joseph (the only operator) knows what to do without re-reading the spec

**Acceptance Criteria:**
- Given an AWS account with credentials configured locally and `GITHUB_PAT`/`CLAUDE_API_KEY` set as env vars, when `provision_secrets_storage.py` is run, then both SSM `SecureString` parameters exist with the supplied values and an S3 bucket exists for Run Logs.
- Given the script has already run once successfully, when it is run again unchanged, then it exits 0 without erroring or creating duplicate resources.
- Given no AWS credentials are configured, when the script is run, then it exits non-zero before attempting to create anything, with a message telling the operator to run `aws configure`.
- Given neither `GITHUB_PAT` nor `CLAUDE_API_KEY` is set as an env var, when the script is run interactively, then it prompts for each via `getpass` (not `input()`, so the value is not echoed) rather than failing outright.

## Design Notes

SSM parameter names: `/agent-orchestrator/github-pat` and `/agent-orchestrator/claude-api-key`, both `Type=SecureString` using the default `alias/aws/ssm` KMS key (no custom CMK — avoids any KMS cost). S3 bucket name: `{account-id}-agent-orchestrator-run-logs`, derived at runtime via `sts:GetCallerIdentity` so it never collides with another AWS account's global bucket namespace. Bucket gets `PublicAccessBlockConfiguration` (all four flags true) and a bucket policy denying any request where `aws:SecureTransport` is `false`.

## Verification

**Commands:**
- `python agent-orchestrator/scripts/provision_secrets_storage.py` -- expected: exits 0, prints the two SSM parameter names and the bucket name it created/confirmed
- `aws ssm get-parameter --name /agent-orchestrator/github-pat --with-decryption --query Parameter.Value` -- expected: returns the value that was supplied (manual spot-check, not part of the script)
- `aws s3api get-public-access-block --bucket {account-id}-agent-orchestrator-run-logs` -- expected: all four block-public-access flags `true`

Live-verified 2026-09-02: both SSM parameters confirmed via `aws ssm get-parameter` (existence/type only, no decryption), and the S3 bucket confirmed via `get-public-access-block`, `get-bucket-encryption`, and `get-bucket-policy`. Script run twice by Joseph, confirming idempotency (second run: "S3 bucket already exists", no errors).

## Suggested Review Order

**Entry point & provisioning flow**

- Orchestrates the whole run: credential check → secrets → SSM → S3, wrapped in one error boundary.
  [`provision_secrets_storage.py:140`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L140)

- Fails fast with a resumable message before touching AWS, rather than a raw traceback.
  [`provision_secrets_storage.py:22`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L22)

**Secret handling**

- Strips whitespace and rejects empty values from both env var and hidden prompt paths.
  [`provision_secrets_storage.py:37`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L37)

- Idempotent SSM write via `Overwrite=True` — safe to re-run without erroring.
  [`provision_secrets_storage.py:52`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L52)

**S3 bucket hardening & idempotency**

- TOCTOU-safe: catches `BucketAlreadyOwnedByYou` on create, not just the existence pre-check.
  [`provision_secrets_storage.py:63`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L63)

- Public access block, default SSE-S3 encryption, and TLS-only policy applied unconditionally on every run.
  [`provision_secrets_storage.py:97`](../../../agent-orchestrator/scripts/provision_secrets_storage.py#L97)
