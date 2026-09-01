# agent-orchestrator

Autonomous Claude agent pipeline (LangGraph-style node graph) that resolves a
GitHub Issue on `self-management-app` end to end, with no human in the loop.
See `../planning/_bmad-output/planning-artifacts/architecture/architecture-planning-2026-09-01/ARCHITECTURE-SPINE.md`
for the binding design.

## Story 1.1: Secrets & Storage Scaffolding

Run this once (and safely re-run any time) to provision the SSM parameters
and S3 bucket every later story depends on.

**Prerequisites:**
- AWS CLI configured (`aws configure`) with an IAM identity that can create
  SSM parameters and S3 buckets.
- Python 3.12+ with `pip install -r requirements.txt`.

**Required secrets** (never pass these as CLI arguments):
- `GITHUB_PAT` — a fine-grained GitHub PAT scoped to `self-management-app`
  with Contents (read/write) and Issues (read/write) permissions.
- `CLAUDE_API_KEY` — an Anthropic API key.

Set both as environment variables before running, or leave them unset and
the script will prompt for each with hidden input:

```bash
export GITHUB_PAT=...
export CLAUDE_API_KEY=...
python scripts/provision_secrets_storage.py
```

On success it prints the two SSM parameter names and the S3 bucket name it
created or confirmed. Nothing is written to disk in plaintext.

## Story 1.2: Trigger Lambda — Ticket Detection

Run once (safely re-runnable) after Story 1.1. Creates the on-demand EC2
orchestrator instance (stopped baseline, no SSH — SSM Session Manager only),
its IAM role and security group, the trigger Lambda, and an EventBridge
5-minute schedule that invokes it.

**Prerequisites:** same AWS credentials as Story 1.1. No new secrets needed.

```bash
python scripts/provision_trigger_infra.py
```

On success it prints the EC2 instance id, Lambda function name, and
EventBridge rule name. The instance boots immediately after creation to
prove the start/self-stop mechanism works, then stops itself within about a
minute (there's no `bootstrap/run.sh` in the Run Log bucket yet — that
arrives in Story 1.3).

**How detection works:** every 5 minutes the Lambda polls GitHub for the
oldest open issue labeled `agent-ready`, claims it by swapping the label to
`agent-processing`, tags the EC2 instance with the issue number, and starts
it. If a claim partially fails (e.g. GitHub rejects the second half of the
label swap, or the EC2 start call fails), the Lambda rolls the label back to
`agent-ready` so the same issue is retried on the next poll rather than
getting stuck.

**Manual verification:**
```bash
aws lambda invoke --function-name agent-orchestrator-trigger --payload '{}' /tmp/out.json && cat /tmp/out.json
```
