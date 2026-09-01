# Deferred Work

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-secrets-storage-scaffolding.md`
  summary: Add a lifecycle/expiration policy to the Run Log S3 bucket so logs don't accumulate indefinitely.
  evidence: Review flagged unbounded storage growth with no cost control; not required by Story 1.1's AC, worth revisiting once real Run volume is known.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-secrets-storage-scaffolding.md`
  summary: Document a least-privilege IAM policy for the EC2/Lambda roles that will read these SSM secrets, once those roles exist.
  evidence: Story 1.1 deliberately doesn't create IAM roles (that's Stories 1.2/1.3); the exact `ssm:GetParameter` scoping should be defined when those roles are built, not guessed now.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-trigger-lambda-ticket-detection.md`
  summary: Add a distributed lock (e.g. a DynamoDB conditional write) around the check-then-act sequence in the trigger Lambda to fully close the race window between two overlapping invocations.
  evidence: Review flagged that two concurrent invocations could both observe "instance not running" before either completes its claim. Low probability at hobby scale (single 5-minute EventBridge schedule, no manual concurrent triggering), and the claim-rollback logic added in this story's patch pass makes any resulting stuck state self-heal on the next poll rather than being catastrophic. Worth closing properly if usage ever becomes less solo/occasional.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-trigger-lambda-ticket-detection.md`
  summary: Write a teardown/decommission script for the trigger infrastructure (EC2 instance, IAM roles, security group, Lambda, EventBridge rule).
  evidence: Review flagged that `provision_trigger_infra.py` only creates/updates resources, with no corresponding reversal path for cost control or environment reset. Not needed for MVP; worth adding once the pipeline is stable and Joseph wants to reset/rebuild the stack.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-orchestrator-bootstrap.md`
  summary: Add log rotation/truncation for /var/log/agent-orchestrator-run.log on the EC2 instance.
  evidence: Review flagged the log grows unbounded across every boot with no size cap. Negligible at hobby scale over the near term; worth adding if the instance runs for a long time without being replaced.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-orchestrator-bootstrap.md`
  summary: Verify the uploaded run.sh in S3 matches the local file (e.g. ETag/hash check) after upload_bootstrap_script.py runs.
  evidence: Review flagged that "idempotent upload" is asserted but not confirmed post-upload. The added bash -n lint-before-upload check catches syntax errors, which was the main risk; full content verification is lower priority.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-runstate-clients-spend-ledger.md`
  summary: Add real file locking (not just atomic writes) around SpendLedger.record_call() to close the read-modify-write race between two concurrent writers.
  evidence: Review flagged that two interleaved record_call() invocations could each read before either writes, silently dropping one entry. Atomic temp-file-then-rename writes (implemented) prevent corruption from a crash mid-write, but don't close the interleaving race. Low probability given the system runs one Run at a time by design (PRD explicitly defers concurrency); worth closing if that assumption ever changes.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-runstate-clients-spend-ledger.md`
  summary: Recover/log spend if a Claude API call is billed server-side but the client never receives a usable response (e.g. connection drops after processing).
  evidence: Review flagged this as a way real spend could go unrecorded, undercounting the ledger against the true RM100 cap. No general fix exists without an Anthropic-side usage-reconciliation API; accepted as a known small residual risk for now.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-runstate-clients-spend-ledger.md`
  summary: Have GitHubClient.push() fetch/rebase before pushing, and let Locate/Implement pass an explicit path scope instead of defaulting to `git add -A`.
  evidence: Review flagged both as real gaps for a no-review-gate push straight to main. Low risk today (solo system, one Run at a time, working copy freshly reset per AD-5 before each Run) -- push() already accepts an optional `paths` param for future stories to use once Locate's file_targets are available to pass through.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-runstate-clients-spend-ledger.md`
  summary: Add status/current-node/timestamp fields to RunState for resumability and stuck-run detection.
  evidence: Review flagged RunState has no way to tell which node a run is in or when it started. AD-1 fixes RunState's field list explicitly; adding fields needs an architecture amendment, not a unilateral change mid-story. Revisit when Stories 1.5-1.7 build the actual node graph and need this.
