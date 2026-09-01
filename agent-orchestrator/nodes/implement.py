"""Implement node: writes the actual code change for every file Locate
approved. Never writes outside state.file_targets, even if a Claude
response suggests a different path -- Locate's approval is the only
authority for what may change, but this module also independently
re-checks the denylist and confines every write inside repo_dir as
defense-in-depth, since a write here is closer to an eventual unreviewed
push than most other places in the pipeline.
"""

import logging
import os
import subprocess

from clients.claude_client import ClaudeClient
from denylist import ScopeViolation, is_denylisted
from state import RunState

logger = logging.getLogger(__name__)

DIFF_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = """You are the implementation step of an autonomous coding \
agent. Given a change plan and one file's current content, respond with \
ONLY the complete new content for that file -- the whole file, not a \
diff or patch, including every unchanged line. Make only the changes the \
plan calls for; do not refactor, rename, or "improve" anything the plan \
doesn't ask for. Respond with the raw file content and nothing else -- no \
markdown code fences, no explanation, no commentary before or after."""


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    starts_fenced = stripped.startswith("```")
    if not starts_fenced:
        return text  # real file content -- preserve exactly, including trailing newline
    if not stripped.endswith("```") or len(stripped) < 6:
        raise ScopeViolation(
            "Implement's response looks like a truncated/malformed code "
            "fence (starts with ``` but doesn't cleanly close) -- refusing "
            "to write it, since it would corrupt the file."
        )
    inner = stripped[3:-3]
    first_newline = inner.find("\n")
    if first_newline != -1 and len(inner[:first_newline].strip()) <= 20:
        inner = inner[first_newline + 1 :]
    return inner


def _resolve_safe_path(repo_dir: str, path: str) -> str:
    """Confines the write to inside repo_dir, independent of whatever
    Locate already checked -- a defense-in-depth boundary, not a
    substitute for Locate's approval."""
    repo_real = os.path.realpath(repo_dir)
    full_path = os.path.realpath(os.path.join(repo_dir, path))
    if full_path != repo_real and not full_path.startswith(repo_real + os.sep):
        raise ScopeViolation(
            f"Implement target '{path}' resolves outside the repository "
            f"({full_path}) -- refusing to write it."
        )
    matched = is_denylisted(path)
    if matched:
        raise ScopeViolation(
            f"Implement target '{path}' matches denylisted pattern "
            f"'{matched}' -- refusing to write it (Locate should have "
            "caught this; this is the second, independent check)."
        )
    return full_path


def _implement_one_file(
    plan: str, path: str, repo_dir: str, claude_client: ClaudeClient, feedback: str = ""
) -> None:
    full_path = _resolve_safe_path(repo_dir, path)

    current_content = ""
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()
        except (UnicodeDecodeError, IsADirectoryError, OSError) as exc:
            raise ScopeViolation(f"Cannot read '{path}' to implement it: {exc}") from exc

    user_message = f"Change plan:\n{plan}\n\n"
    if feedback:
        user_message += (
            f"A previous attempt's tests failed with this output -- fix "
            f"the actual problem, don't just repeat the same change:\n"
            f"{feedback}\n\n"
        )
    user_message += f"File: {path}\n\nCurrent content:\n{current_content}"

    try:
        new_content = claude_client.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=8192,
            node="implement",
        )
    except Exception as exc:
        raise RuntimeError(f"Implement's Claude call failed for '{path}': {exc}") from exc

    new_content = _strip_code_fence(new_content)
    if not new_content.strip():
        raise ScopeViolation(
            f"Implement's response for '{path}' was empty -- refusing to "
            "overwrite the file with nothing."
        )

    dirpath = os.path.dirname(full_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    logger.info("Implemented change to %s", path)


def implement(
    state: RunState, claude_client: ClaudeClient, repo_dir: str, feedback: str = ""
) -> RunState:
    if not state.file_targets:
        raise ValueError("Cannot implement: state.file_targets is empty")

    state.diff = ""  # never leave a stale diff from a prior attempt in place

    for path in state.file_targets:
        _implement_one_file(state.plan, path, repo_dir, claude_client, feedback)

    diff = subprocess.run(
        ["git", "-C", repo_dir, "diff"],
        capture_output=True,
        text=True,
        timeout=DIFF_TIMEOUT_SECONDS,
    )
    if diff.returncode == 0:
        state.diff = diff.stdout
    else:
        logger.warning("Could not compute git diff in %s: %s", repo_dir, diff.stderr)
    return state
