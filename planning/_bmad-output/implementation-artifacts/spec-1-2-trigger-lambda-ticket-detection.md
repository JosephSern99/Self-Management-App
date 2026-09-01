---
title: 'Story 1.2: Trigger Lambda — Ticket Detection'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'd782c07766d0e87cb6b01389fa2aa641f0011dd2'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing currently detects a Ticket (a GitHub Issue labeled `agent-ready`) or has anywhere to run it — no Lambda, no EventBridge schedule, and no EC2 instance exists yet for it to start.

**Approach:** A one-time provisioning script creates the EC2 orchestrator instance (stopped baseline, SSM-managed, no SSH), an IAM role + security group for it, and deploys a Lambda (polled every 5 minutes by EventBridge) that finds an `agent-ready` issue, atomically claims it by swapping its label to `agent-processing`, tags the instance with the issue number, and starts it.

## Boundaries & Constraints

**Always:** Label-swap (`agent-ready` → `agent-processing`) happens before starting the instance, so a Run is claimed exactly once even if Lambda fires again before the instance finishes booting. The EC2 instance boots with a minimal user-data stub that fetches and runs `s3://{run-log-bucket}/bootstrap/run.sh`; if that object doesn't exist yet (later stories not built), it logs that and self-stops via `shutdown -h now` — never terminates, never loops. No SSH key pair is created; the instance is reachable only via SSM Session Manager (`AmazonSSMManagedInstanceCore`) for manual debugging. Security group has no inbound rules.

**Ask First:** Nothing requires a mid-execution human decision — Joseph runs the provisioning script himself with his already-configured AWS credentials, same as Story 1.1.

**Never:** Do not write the real orchestrator bootstrap logic (`run.sh` content) in this story — that's Story 1.3. Do not create an SSH key pair or open any inbound security group rule. Do not use PyGithub or any Lambda dependency layer — call the GitHub REST API directly via `urllib` (stdlib only) so the Lambda needs zero deployment package dependencies.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| New Ticket, instance stopped | One open issue labeled `agent-ready`; EC2 instance state = stopped | Label swapped to `agent-processing`; instance tagged with issue number; `StartInstances` called | N/A |
| No matching issue | No open issue has `agent-ready` | Lambda logs "no ticket found" and exits cleanly, no AWS mutation | N/A |
| Instance already running | An issue is already `agent-processing` and instance state = running | Lambda does not start a second Run; logs "Run already in progress, skipping" | N/A |
| Multiple `agent-ready` issues at once | 2+ open issues labeled `agent-ready` | Only the oldest (lowest issue number) is claimed this poll; the rest wait for a future poll after the instance frees up | N/A |
| GitHub API call fails | Transient 5xx or rate-limit from GitHub | Lambda logs the error and exits without mutating EC2 state, so the next poll retries cleanly | Lambda run reports failure in CloudWatch Logs; no partial label swap without a start |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/trigger_lambda/handler.py` -- new: Lambda entrypoint (poll, claim, tag, start)
- `agent-orchestrator/scripts/provision_trigger_infra.py` -- new: one-time provisioning (IAM roles, security group, EC2 instance, Lambda deploy, EventBridge rule)
- `agent-orchestrator/scripts/provision_secrets_storage.py` -- reference only: same idempotent-script pattern and `get_secret`/credential-check style to follow (from Story 1.1)
- `agent-orchestrator/README.md` -- update: document Story 1.2's provisioning step

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/trigger_lambda/handler.py` -- implement per I/O Matrix -- polls GitHub via `urllib` using the SSM-stored PAT, claims via label swap, tags + starts EC2
- [x] `agent-orchestrator/scripts/provision_trigger_infra.py` -- implement per Boundaries -- creates EC2 IAM role/security group/instance (stopped baseline), Lambda IAM role, deploys Lambda, creates EventBridge 5-minute schedule; idempotent (safe re-run)
- [x] `agent-orchestrator/README.md` -- document the new provisioning step and what it creates

**Acceptance Criteria:**
- Given an open GitHub issue labeled `agent-ready` and no Run in progress, when the Lambda runs (invoked manually for verification), then the issue's label becomes `agent-processing`, the EC2 instance is tagged with the issue number, and the instance transitions to running.
- Given an issue without the `agent-ready` label, when the Lambda runs, then no AWS or GitHub mutation occurs.
- Given the EC2 instance is already running, when the Lambda runs again, then it does not call `StartInstances` a second time.
- Given the provisioning script has already run once, when it is run again unchanged, then it exits 0 without erroring or duplicating resources.

## Design Notes

The Lambda's IAM execution role and the EC2 instance profile's IAM role both start minimal (SSM read on `/agent-orchestrator/*`, plus what this story needs) and are expected to gain additional inline-policy statements in later stories (1.4 needs S3 write for Run Logs, etc.) — `provision_trigger_infra.py` should attach policy statements idempotently (re-applying the same policy document) rather than assuming a fixed final shape now.

EC2 AMI is resolved at provisioning time via the public SSM parameter `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64` rather than a hardcoded AMI id, so re-running the script later still picks a current AMI.

The instance boots, fetches `bootstrap/run.sh` from the Run Log bucket (created in Story 1.1), and self-stops if that key is absent — this means running the provisioning script today will visibly start and then stop the instance within roughly a minute, which is expected and a useful live proof the start/stop mechanism works before Story 1.3 exists.

## Verification

**Commands:**
- `python agent-orchestrator/scripts/provision_trigger_infra.py` -- expected: exits 0, prints the EC2 instance id, Lambda function name, and EventBridge rule name
- `aws lambda invoke --function-name agent-orchestrator-trigger --payload '{}' /tmp/out.json && cat /tmp/out.json` -- expected: 200 response, log output shows either a claimed issue or "no ticket found"
- `aws ec2 describe-instances --instance-ids {id} --query "Reservations[0].Instances[0].State.Name"` -- expected: `stopped` at rest, `running` briefly after a successful trigger

Live-verified 2026-09-02: `provision_trigger_infra.py` run (one retry needed for IAM instance-profile propagation lag, confirmed idempotent on re-run). Instance `i-0db16fa88f72617a7` launched, ran its bootstrap stub (no `run.sh` in the bucket yet, as expected pre-Story-1.3), and self-stopped within ~1 minute -- directly confirms the `set -e` bootstrap bug fix works. Lambda invoked both manually and via the live EventBridge schedule; CloudWatch logs confirm correct `"No ticket found."` behavior with no errors, since no real Ticket has been filed yet.

## Suggested Review Order

**Claim safety (the core correctness concern)**

- Roll-back-on-failure logic that keeps a Ticket claim from getting permanently stuck.
  [`handler.py:106`](../../../agent-orchestrator/trigger_lambda/handler.py#L106)

- Best-effort rollback if AWS itself fails after GitHub's half of the claim already succeeded.
  [`handler.py:126`](../../../agent-orchestrator/trigger_lambda/handler.py#L126)

**Cost-model correctness**

- The bootstrap script fix: `run.sh` failure must never block the trailing `shutdown -h now`.
  [`provision_trigger_infra.py:180`](../../../agent-orchestrator/scripts/provision_trigger_infra.py#L180)

- On-demand start guarded against the `stopping`/`shutting-down` transition window.
  [`handler.py:28`](../../../agent-orchestrator/trigger_lambda/handler.py#L28)

**Provisioning & least privilege**

- Self-stop permission scoped to this one instance only, applied after it exists.
  [`provision_trigger_infra.py:124`](../../../agent-orchestrator/scripts/provision_trigger_infra.py#L124)

- Entry point tying the whole idempotent provisioning sequence together.
  [`provision_trigger_infra.py:384`](../../../agent-orchestrator/scripts/provision_trigger_infra.py#L384)
