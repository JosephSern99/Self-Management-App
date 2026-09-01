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
