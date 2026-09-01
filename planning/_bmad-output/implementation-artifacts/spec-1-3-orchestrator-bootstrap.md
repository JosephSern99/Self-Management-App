---
title: 'Story 1.3: Orchestrator Bootstrap & Clean Working Copy'
type: 'feature'
created: '2026-09-02'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'c4d80ebac77585baec9fbce17b538fd16acef2d8'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 1.2's EC2 instance boots and looks for `s3://{bucket}/bootstrap/run.sh` but that object doesn't exist yet, so it just logs a message and self-stops. There's also no repo working copy on the instance at all yet.

**Approach:** A `run.sh` script (uploaded to S3 by a small provisioning script) that, on every boot: clones the repo if it's the instance's first boot, or fetches + hard-resets + cleans an existing clone otherwise; reads which issue it's processing from the instance's own `CurrentIssueNumber` tag; repeats the reset/clean at the end regardless of outcome. The outer bootstrap stub (already built in Story 1.2) handles `shutdown -h now` no matter how `run.sh` exits, so this story doesn't touch that contract.

## Boundaries & Constraints

**Always:** The working copy is reset with both `git reset --hard origin/main` *and* `git clean -fd` before anything runs and again at the end — a hard reset alone doesn't remove untracked files, and AD-5 requires the copy is never left dirty. The repo clone/fetch/push all authenticate via the GitHub PAT already in SSM (`/agent-orchestrator/github-pat`) — never prompt, never require SSH keys. The working copy lives at a fixed path (`/opt/agent-orchestrator/repo`) that persists across instance stop/start (EBS-backed, not `/tmp`).

**Ask First:** Nothing requires a mid-execution human decision.

**Never:** Do not implement the actual LangGraph node graph in this story (Plan/Locate/Implement/Test/Self-Review/Push are Stories 1.4–1.7) — `run.sh` at this stage only proves the clean-checkout lifecycle and logs which issue it would process. Do not install PHP/Composer or any Laravel test dependencies here — that's Story 1.6's concern, scoped to when the Test node actually needs it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First boot ever | `/opt/agent-orchestrator/repo` does not exist | `git clone` the repo using the SSM-stored PAT | If clone fails, log the error and exit non-zero (outer stub still self-stops) |
| Subsequent boot, clean prior end | Working copy exists, was reset+cleaned at the end of the previous run | `git fetch && git reset --hard origin/main && git clean -fd` brings it to current `main` | N/A |
| Subsequent boot, prior run crashed mid-Implement (untracked files left) | Working copy has stray untracked files from an interrupted prior run | The same reset+clean sequence removes them before this run starts | N/A |
| Instance has no `CurrentIssueNumber` tag | Boot triggered manually/for testing, no tag set by Lambda | Script logs "no issue tag found" and still performs the reset lifecycle, then exits cleanly | Not treated as a failure -- reset/clean must still happen |
| GitHub auth fails (PAT revoked/expired) | `git fetch`/`git clone` rejected | Script logs the failure clearly and exits non-zero; working copy is left in its last-known state rather than partially modified | N/A |

</frozen-after-approval>

## Code Map

- `agent-orchestrator/bootstrap/run.sh` -- new: the script Story 1.2's instance fetches from S3 and executes on every boot
- `agent-orchestrator/scripts/upload_bootstrap_script.py` -- new: idempotent uploader, `run.sh` -> `s3://{bucket}/bootstrap/run.sh`
- `agent-orchestrator/scripts/provision_trigger_infra.py` -- reference only (Story 1.2): defines `bootstrap_user_data()`, the outer stub this story's `run.sh` is fetched and run by; not modified here
- `agent-orchestrator/README.md` -- update: document the upload step

## Tasks & Acceptance

**Execution:**
- [x] `agent-orchestrator/bootstrap/run.sh` -- implement per I/O Matrix -- clone-or-reset+clean the working copy, read the issue tag via instance metadata + `ec2:DescribeTags`, log status, repeat reset+clean at the end
- [x] `agent-orchestrator/scripts/upload_bootstrap_script.py` -- implement -- idempotent S3 upload of `run.sh` (safe to re-run any time `run.sh` changes)
- [x] `agent-orchestrator/README.md` -- document running the uploader after any `run.sh` change
- [x] `agent-orchestrator/scripts/provision_trigger_infra.py` -- amended (out-of-scope-file exception, see Spec Change Log) -- `bootstrap_user_data()` now installs `git` + a systemd oneshot unit instead of assuming user-data re-executes every boot

**Acceptance Criteria:**
- Given the EC2 instance's first-ever boot after `run.sh` is uploaded, when the instance starts (via Lambda or manual `StartInstances`), then `/opt/agent-orchestrator/repo` is cloned fresh from `main`.
- Given a subsequent boot with an existing working copy (including one with leftover untracked files from an interrupted prior run), when the instance starts, then the working copy matches `origin/main` exactly with no untracked files remaining, both before and after the (currently no-op) run body.
- Given the instance was started by Story 1.2's Lambda for a specific issue, when `run.sh` runs, then it reads and logs that issue number from the instance's own `CurrentIssueNumber` tag.
- Given `run.sh` completes (success or failure), when it exits, then the instance still self-stops shortly after (verifying Story 1.2's outer stub contract still holds unchanged).

## Spec Change Log

- 2026-09-02: Live testing revealed EC2 user-data (cloud-init's `scripts-user` module) runs only once per instance lifetime, not on every start -- the entire on-demand Run lifecycle (AD-3/AD-4/AD-5) silently did nothing after the first boot. Amended `agent-orchestrator/scripts/provision_trigger_infra.py`'s `bootstrap_user_data()` (a Story 1.2 file, touched here because the fix is inseparable from proving Story 1.3's lifecycle works) to install `git` and a systemd oneshot unit on first boot instead, with the unit re-firing on every subsequent boot via `systemctl enable`. Recorded as Architecture AD-11. KEEP: the existing instance was terminated and recreated via the idempotent provisioning script rather than patched in place, since cloud-init's once-per-instance semaphore can't be reset non-destructively.
- 2026-09-02: Also fixed during implementation (not a spec change, noted for completeness): the GitHub PAT is scrubbed from `.git/config` after every clone/fetch (reset to a credential-less remote URL) and redacted from `run.sh`'s log output, since git echoes the failing remote URL verbatim on auth errors.

## Design Notes

Reading the instance's own tag requires the instance to know its own instance-id, available via the EC2 instance metadata service (`http://169.254.169.254/latest/meta-data/instance-id`, IMDSv2 token flow) — no AWS credentials needed for that call, but the subsequent `aws ec2 describe-tags` call uses the instance role's credentials already granted `ec2:DescribeTags` in Story 1.2.

Once Stories 1.4–1.7 exist, `run.sh` will be extended to invoke the actual Python orchestrator (`orchestrator.py`) after the initial reset and before the final reset — this story only builds the lifecycle scaffold around that future call, marked with a clear placeholder comment.

## Verification

**Commands:**
- `python agent-orchestrator/scripts/upload_bootstrap_script.py` -- expected: exits 0, confirms `run.sh` uploaded to the Run Log bucket
- `aws ec2 start-instances --instance-ids {id}` then poll `describe-instances` -- expected: instance transitions running -> stopped within a couple of minutes
- `aws logs tail /aws/lambda/agent-orchestrator-trigger --since 5m` and instance system log (`aws ec2 get-console-output --instance-id {id}`) -- expected: console output shows the clone/reset lifecycle log lines

Live-verified 2026-09-02 via SSM Session Manager (console output proved unreliable on AL2023; used `aws ssm send-command` instead). Across 3 stop/start cycles on the recreated instance (`i-0f1786cb7f929bdad`): first boot installed `git` and cloned the repo fresh; a subsequent boot correctly took the fetch+reset+clean path and reported `HEAD is now at 03153be sync changes` (the real, current state of `origin/main` -- confirming this local session's commits haven't been pushed to GitHub yet, a separate finding surfaced to Joseph); `CurrentIssueNumber` tag absence was correctly logged and handled as a no-op boot; the instance self-stopped within roughly a minute each time via the new systemd-driven mechanism. `.git/config` confirmed to contain a clean, credential-less origin URL after every run.

## Suggested Review Order

**The critical fix (start here)**

- Why user-data alone can't drive every-boot logic, and the systemd unit that replaces it.
  [`provision_trigger_infra.py:180`](../../../agent-orchestrator/scripts/provision_trigger_infra.py#L180)

**Credential safety**

- PAT only ever touches a remote URL for the single command that needs it, then the remote is scrubbed.
  [`run.sh:103`](../../../agent-orchestrator/bootstrap/run.sh#L103)

- Redaction filter preventing the PAT from landing in the log on a git auth failure.
  [`run.sh:21`](../../../agent-orchestrator/bootstrap/run.sh#L21)

**Lifecycle correctness**

- Corrupt/partial working copy is discarded rather than silently reused forever.
  [`run.sh:71`](../../../agent-orchestrator/bootstrap/run.sh#L71)

- Entry point tying together PAT retrieval, issue detection, and the before/after reset.
  [`run.sh:126`](../../../agent-orchestrator/bootstrap/run.sh#L126)
