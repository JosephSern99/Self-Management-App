"""The orchestrator entrypoint: wires all six nodes (Plan, Locate, Implement,
Test, Self-Review, Push) into the single linear sequence that resolves one
GitHub issue end to end. Not a LangGraph graph -- the real pipeline has no
branching beyond Test's own already-self-contained implement-retry loop, so
a plain Python function satisfies Architecture AD-1's "single Python
orchestrator process per Run" with none of a graph-execution framework's
extra operational risk. This is a deliberate, logged deviation from the
spine's stated LangGraph paradigm, not a silent one.

Spend Cap (Architecture AD-8) is checked before the Run starts at all, and
again before every node boundary -- a cap crossed mid-Run aborts before the
*next* node, never mid-node. A RunLog is persisted exactly once per Run
regardless of how it ends; a failure persisting it is logged, never allowed
to mask the Run's real outcome.
"""

import argparse
import logging
import sys
import uuid

import boto3

from clients.claude_client import ClaudeClient
from clients.github_client import GitHubClient
from denylist import ScopeViolation
from nodes.implement import implement
from nodes.locate import locate
from nodes.plan import plan
from nodes.push import push
from nodes.self_review import SelfReviewRejected, self_review
from nodes.test import TestsFailedAfterRetries, test_and_retry
from run_log import RunLog, RunLogPersistError, persist_run_log
from spend_ledger import SpendCapExceeded, SpendLedger
from state import RunState

logger = logging.getLogger(__name__)

DEFAULT_REPO_DIR = "/opt/agent-orchestrator/repo"


def _resolve_run_log_bucket_name(sts_client=None) -> str:
    """Same naming convention as provision_secrets_storage.py's Run Log
    bucket -- fully determined by the AWS account, which every other AWS
    call this process makes already requires, so there's nothing to
    hardcode or configure separately."""
    sts = sts_client or boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    return f"{account_id}-agent-orchestrator-run-logs"


def _cap_exceeded_reason(spend_ledger: SpendLedger, next_node: str) -> str:
    return (
        f"Spend cap reached before node '{next_node}' could run "
        f"(cumulative spend RM{spend_ledger.total_spend_myr():.2f})."
    )


def _best_effort_failure_comment(github_client: GitHubClient, issue_number: int, reason: str) -> None:
    """Never allowed to raise past this function -- a GitHub API hiccup
    while reporting a failure must not itself prevent finalize()/
    persist_run_log() from still running. Without this, a failed Run
    leaves no visibility short of manually checking S3 or EC2 logs."""
    try:
        github_client.comment_issue(
            issue_number,
            "Autonomous agent run failed and made no changes (or the "
            f"change was never pushed).\n\n**Reason:** {reason}",
        )
    except Exception as exc:
        logger.error("Could not post failure comment to issue #%s: %s", issue_number, exc)


def _persist(run_log: RunLog, outcome: str, reason: str) -> None:
    run_log.finalize(outcome, reason)
    try:
        bucket_name = _resolve_run_log_bucket_name()
        persist_run_log(run_log, bucket_name)
    except RunLogPersistError as exc:
        logger.error("Failed to persist run log for run %s: %s", run_log.run_id, exc)
    except Exception as exc:
        # Covers e.g. STS get_caller_identity failing before a bucket name
        # can even be determined -- still must not raise past run().
        logger.error(
            "Could not resolve run log bucket / persist run log for run %s: %s",
            run_log.run_id,
            exc,
        )


def run(issue_number: int, repo_dir: str = DEFAULT_REPO_DIR) -> str:
    run_id = str(uuid.uuid4())
    spend_ledger = SpendLedger()
    run_log = RunLog(run_id=run_id, issue_number=issue_number)

    outcome = "failed"
    reason = ""
    github_client = None

    if not spend_ledger.can_start_new_run():
        outcome = "aborted"
        reason = _cap_exceeded_reason(spend_ledger, "plan")
        logger.warning("Run %s aborted before start: %s", run_id, reason)
        _persist(run_log, outcome, reason)
        return outcome

    try:
        github_client = GitHubClient()
        issue = github_client.get_issue(issue_number)
        state = RunState(run_id=run_id, ticket=issue)
        claude_client = ClaudeClient(spend_ledger=spend_ledger, run_id=run_id)

        node_sequence = [
            ("plan", lambda s: plan(s, claude_client)),
            ("locate", lambda s: locate(s, claude_client, repo_dir)),
            ("implement", lambda s: implement(s, claude_client, repo_dir)),
            ("test", lambda s: test_and_retry(s, claude_client, repo_dir)),
            ("self_review", lambda s: self_review(s, claude_client, repo_dir)),
            ("push", lambda s: push(s, github_client, repo_dir)),
        ]

        for node_name, node_fn in node_sequence:
            if not spend_ledger.can_start_new_run():
                outcome = "aborted"
                reason = _cap_exceeded_reason(spend_ledger, node_name)
                logger.warning("Run %s aborted mid-run: %s", run_id, reason)
                break

            try:
                state = node_fn(state)
            except SpendCapExceeded as exc:
                outcome = "aborted"
                reason = str(exc)
                logger.warning("Run %s aborted during '%s': %s", run_id, node_name, reason)
                state.spend_used = spend_ledger.total_spend_myr()
                run_log.record_node(node_name, state)
                break
            except (ScopeViolation, TestsFailedAfterRetries, SelfReviewRejected) as exc:
                outcome = "failed"
                reason = f"{node_name}: {exc}"
                logger.warning("Run %s failed at '%s': %s", run_id, node_name, exc)
                state.spend_used = spend_ledger.total_spend_myr()
                run_log.record_node(node_name, state)
                break
            except Exception as exc:
                outcome = "failed"
                reason = f"{node_name}: unexpected error: {exc}"
                logger.exception("Run %s hit an unexpected error in '%s'", run_id, node_name)
                state.spend_used = spend_ledger.total_spend_myr()
                run_log.record_node(node_name, state)
                break
            else:
                # RunState.spend_used is never written by any node itself
                # (ClaudeClient logs real cost straight to SpendLedger,
                # bypassing RunState) -- the orchestrator is the only place
                # that sees both, so it snapshots the real cumulative total
                # here rather than leaving the field permanently at its 0.0
                # default in every persisted RunLog entry.
                state.spend_used = spend_ledger.total_spend_myr()
                run_log.record_node(node_name, state)
        else:
            outcome = "success"
            reason = ""

    except Exception as exc:
        # Anything before/outside the node loop itself -- e.g. fetching the
        # issue, constructing a client -- is still a Run that didn't
        # complete, not a special case.
        outcome = "failed"
        reason = f"Run setup failed: {exc}"
        logger.exception("Run %s failed during setup", run_id)

    if outcome == "failed" and github_client is not None:
        _best_effort_failure_comment(github_client, issue_number, reason)

    _persist(run_log, outcome, reason)
    return outcome


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Run the agent-orchestrator pipeline for one GitHub issue."
    )
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number to resolve.")
    parser.add_argument(
        "--repo-dir",
        type=str,
        default=DEFAULT_REPO_DIR,
        help=f"Path to the working copy (default: {DEFAULT_REPO_DIR}).",
    )
    args = parser.parse_args()

    outcome = run(args.issue, args.repo_dir)
    logger.info("Run finished with outcome: %s", outcome)
    # Distinct exit codes so a process/monitor watching this instance's exit
    # status can tell a benign, expected abort (spend cap reached) apart
    # from an actual failure (bug, exception, guardrail rejection) without
    # having to pull the S3 RunLog.
    exit_codes = {"success": 0, "failed": 1, "aborted": 2}
    sys.exit(exit_codes.get(outcome, 1))


if __name__ == "__main__":
    main()
