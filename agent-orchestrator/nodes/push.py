"""Push node: the final step. Re-derives the actual changed-file list from
git (never state.file_targets, which is only what Locate planned -- an
Implement retry could in principle have drifted from that list), re-checks
every one against the denylist independently of Locate's earlier check,
then commits, pushes straight to main, and closes out the GitHub issue.

There is no human approval gate before this push, so this second denylist
check is the last line of defense (Architecture AD-7/FR5) -- it must catch
drift Locate never saw.
"""

import logging
import subprocess

from clients.github_client import GitHubClient
from denylist import ScopeViolation, is_denylisted
from state import RunState

logger = logging.getLogger(__name__)

DIFF_TIMEOUT_SECONDS = 30


def _diffed_files(repo_dir: str) -> list[str]:
    """Returns every changed-or-added path in the working copy, tracked or
    not. `git diff --name-only` alone only reports changes to already-
    tracked files, silently missing brand-new files Implement created --
    `git status --porcelain` catches both (`?? path` for untracked, plus
    every other status line) without mutating the index, so the denylist
    check below runs before any git mutation, matching FAIL/denylist-match
    behavior (no add/commit/push)."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=DIFF_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise ScopeViolation(f"Could not determine diffed files in {repo_dir}: {exc}") from exc

    files = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        # Porcelain v1: "XY path" (2-char status, space, path), or
        # "XY old -> new" for renames -- the destination path is what
        # exists in the working copy now, so that's what we check.
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def _build_summary(state: RunState) -> str:
    test_result = state.test_result or {}
    test_status = "passed" if test_result.get("passed") else "unknown"
    return (
        "Autonomous agent self-review passed and this change has been pushed "
        "to main.\n\n"
        f"**Plan:**\n{state.plan}\n\n"
        f"**Test outcome:** {test_status}\n\n"
        f"**Review verdict:** {state.review_verdict}"
    )


def push(state: RunState, github_client: GitHubClient, repo_dir: str) -> RunState:
    # Defense-in-depth: orchestrator.py doesn't exist yet to guarantee call
    # order, so Push must not blindly trust that Self-Review ran and
    # passed -- checked before any git/GitHub call.
    if state.review_verdict != "PASS":
        raise ValueError("Cannot push: self-review did not pass")

    if not state.diff:
        raise ValueError("Cannot push: state.diff is empty")

    changed_files = _diffed_files(repo_dir)
    if not changed_files:
        raise ValueError(
            "Cannot push: git status --porcelain reported no changed files "
            "in the working copy, despite state.diff being non-empty."
        )

    for path in changed_files:
        matched = is_denylisted(path)
        if matched:
            logger.warning(
                "Push blocked: diffed file %s matches denylisted pattern %s",
                path,
                matched,
            )
            raise ScopeViolation(
                f"Push aborted: diffed file '{path}' matches denylisted "
                f"pattern '{matched}' -- refusing to commit or push."
            )

    issue = state.ticket or {}
    issue_number = issue.get("number")
    issue_title = issue.get("title") or ""
    commit_message = f"Fix #{issue_number}: {issue_title}".strip()

    github_client.push(repo_dir, commit_message, paths=changed_files)

    if issue_number is not None:
        github_client.comment_issue(issue_number, _build_summary(state))
        github_client.close_issue(issue_number)

    return state
