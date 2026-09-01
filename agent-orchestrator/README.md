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
