# Deferred Work

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-secrets-storage-scaffolding.md`
  summary: Add a lifecycle/expiration policy to the Run Log S3 bucket so logs don't accumulate indefinitely.
  evidence: Review flagged unbounded storage growth with no cost control; not required by Story 1.1's AC, worth revisiting once real Run volume is known.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-secrets-storage-scaffolding.md`
  summary: Document a least-privilege IAM policy for the EC2/Lambda roles that will read these SSM secrets, once those roles exist.
  evidence: Story 1.1 deliberately doesn't create IAM roles (that's Stories 1.2/1.3); the exact `ssm:GetParameter` scoping should be defined when those roles are built, not guessed now.
