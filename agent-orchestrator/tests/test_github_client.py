"""Tests for GitHubClient.push()'s PAT-leak defense. subprocess.CalledProcessError's
str() includes the full command argv, which for the credentialed set-url/push
steps contains the raw PAT-embedded URL -- push() must never let that leak
verbatim into a raised GitPushError message, since that message can flow into
a persisted RunLog or a public GitHub issue comment."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from clients.github_client import GitHubClient, GitPushError

TOKEN = "ghp_supersecrettoken1234567890"
CREDENTIALED_URL = f"https://x-access-token:{TOKEN}@github.com/JosephSern99/Self-Management-App.git"


def fake_completed(stdout="", returncode=0):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


def _run_side_effect(set_url_fails=False, cleanup_fails=False):
    """Builds a subprocess.run side_effect that walks push()'s real call
    sequence: add, status, branch --show-current, [commit], set-url
    (credentialed), push, set-url (clean)."""
    credentialed_set_url_count = {"n": 0}

    def _run(cmd, **kwargs):
        if cmd[:2] == ["git", "-C"] and "status" in cmd:
            return fake_completed(stdout=" M app/Foo.php\n")
        if "branch" in cmd and "--show-current" in cmd:
            return fake_completed(stdout="main\n")
        if "remote" in cmd and "set-url" in cmd:
            is_credentialed = any(TOKEN in part for part in cmd)
            if is_credentialed:
                credentialed_set_url_count["n"] += 1
                if set_url_fails:
                    raise subprocess.CalledProcessError(1, cmd)
                return fake_completed()
            else:
                if cleanup_fails:
                    raise subprocess.CalledProcessError(1, cmd)
                return fake_completed()
        if "push" in cmd:
            return fake_completed()
        if "rev-parse" in cmd:
            return fake_completed(stdout="abc123\n")
        return fake_completed()

    return _run


def test_push_sanitizes_token_when_credentialed_set_url_fails(tmp_path):
    client = GitHubClient(token=TOKEN)

    with patch(
        "clients.github_client.subprocess.run",
        side_effect=_run_side_effect(set_url_fails=True),
    ):
        with pytest.raises(GitPushError) as exc_info:
            client.push(str(tmp_path), "commit msg", paths=["app/Foo.php"])

    message = str(exc_info.value)
    assert TOKEN not in message
    assert "REDACTED" in message


def test_push_sanitizes_token_when_set_url_and_cleanup_both_fail(tmp_path):
    client = GitHubClient(token=TOKEN)

    with patch(
        "clients.github_client.subprocess.run",
        side_effect=_run_side_effect(set_url_fails=True, cleanup_fails=True),
    ):
        with pytest.raises(GitPushError) as exc_info:
            client.push(str(tmp_path), "commit msg", paths=["app/Foo.php"])

    message = str(exc_info.value)
    assert TOKEN not in message
    assert "REDACTED" in message


def test_push_succeeds_and_returns_head_rev(tmp_path):
    client = GitHubClient(token=TOKEN)

    with patch(
        "clients.github_client.subprocess.run",
        side_effect=_run_side_effect(),
    ):
        rev = client.push(str(tmp_path), "commit msg", paths=["app/Foo.php"])

    assert rev == "abc123"
