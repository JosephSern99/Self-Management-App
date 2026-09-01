"""Locate node: turns Plan's written plan into concrete file targets,
grounded in the real tracked-file list (never a hallucinated path) and
checked against the denylist before the Run is allowed to continue.
"""

import json
import logging
import os
import subprocess

from clients.claude_client import ClaudeClient
from denylist import ScopeViolation, is_denylisted
from state import RunState

logger = logging.getLogger(__name__)

MAX_FILE_TARGETS = 10

SYSTEM_PROMPT = """You are the file-location step of an autonomous coding \
agent. Given a change plan and the complete list of files tracked in the \
repository, respond with ONLY a JSON array of the specific file paths that \
must change to implement the plan. Every path you return MUST be copied \
exactly from the provided file list -- never invent, guess, or slightly \
modify a path. Return the smallest set of files that actually need to \
change. Respond with the JSON array and nothing else -- no markdown code \
fences, no explanation."""


def _list_tracked_files(repo_dir: str) -> list[str]:
    """Uses `ls-files -z` (NUL-separated, unquoted) so filenames with
    spaces, non-ASCII characters, or (in principle) embedded newlines are
    never split incorrectly or C-quoted the way plain `ls-files` output can
    be -- a corrupted path list here would corrupt the membership check
    that Locate's whole safety argument rests on."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ScopeViolation(f"Could not list tracked files in {repo_dir}: {exc}") from exc

    raw = result.stdout.decode("utf-8", errors="replace")
    return [p for p in raw.split("\0") if p]


def _parse_file_list(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScopeViolation(
            f"Locate's response was not valid JSON, refusing to proceed: {exc}"
        ) from exc
    if not isinstance(parsed, list) or not all(isinstance(p, str) for p in parsed):
        raise ScopeViolation(
            "Locate's response was not a JSON array of strings, refusing to proceed."
        )
    return parsed


def locate(state: RunState, claude_client: ClaudeClient, repo_dir: str) -> RunState:
    tracked_files = _list_tracked_files(repo_dir)

    user_message = (
        f"Change plan:\n{state.plan}\n\n"
        f"Tracked files in the repository:\n" + "\n".join(tracked_files)
    )

    try:
        raw_response = claude_client.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1024,
            node="locate",
        )
    except Exception as exc:
        raise ScopeViolation(f"Locate's Claude call failed: {exc}") from exc

    proposed = _parse_file_list(raw_response)

    if not proposed:
        raise ScopeViolation(
            "Locate proposed zero file targets; nothing to safely implement."
        )
    if len(proposed) > MAX_FILE_TARGETS:
        raise ScopeViolation(
            f"Locate proposed {len(proposed)} file targets, exceeding the "
            f"cap of {MAX_FILE_TARGETS} -- refusing an unexpectedly broad "
            "change for a Ticket that should be a scoped, single-feature fix."
        )

    tracked_set = set(tracked_files)
    for path in proposed:
        if path not in tracked_set:
            logger.warning("Locate rejected hallucinated path: %s", path)
            raise ScopeViolation(
                f"Locate proposed '{path}', which is not a tracked file in "
                "the repository -- refusing to proceed on an unverified path."
            )

        matched_pattern = is_denylisted(path)
        if matched_pattern:
            logger.warning(
                "Locate rejected denylisted path: %s (matched pattern: %s)",
                path,
                matched_pattern,
            )
            raise ScopeViolation(
                f"Locate proposed '{path}', which matches denylisted pattern "
                f"'{matched_pattern}' -- refusing to proceed."
            )

        full_path = os.path.join(repo_dir, path)
        if os.path.islink(full_path):
            logger.warning("Locate rejected symlinked path: %s", path)
            raise ScopeViolation(
                f"Locate proposed '{path}', which is a symlink -- refusing "
                "to proceed since its real target can't be verified as safe."
            )

    state.file_targets = proposed
    return state
