import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from denylist import ScopeViolation
from nodes.locate import locate
from state import RunState


@pytest.fixture
def repo_dir(tmp_path):
    """A real git repo with a handful of tracked files, so `git ls-files`
    behaves exactly as it would against the real working copy."""
    d = tmp_path / "repo"
    d.mkdir()
    (d / "app").mkdir()
    (d / "app" / "Http").mkdir()
    (d / "app" / "Http" / "Controllers").mkdir()
    (d / "app" / "Http" / "Controllers" / "FinanceController.php").write_text("<?php")
    (d / "app" / "Http" / "Controllers" / "PaymentController.php").write_text("<?php")
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, check=True)
    return str(d)


def make_state():
    return RunState(run_id="test-run", ticket={"number": 1, "title": "t", "body": "b"}, plan="fix the thing")


def fake_claude_client(response_text: str):
    client = MagicMock()
    client.complete.return_value = response_text
    return client


def test_locate_returns_safe_targets(repo_dir):
    client = fake_claude_client(
        json.dumps(["app/Http/Controllers/FinanceController.php"])
    )
    state = make_state()

    result = locate(state, client, repo_dir)

    assert result.file_targets == ["app/Http/Controllers/FinanceController.php"]


def test_locate_raises_on_denylisted_path(repo_dir):
    client = fake_claude_client(
        json.dumps(["app/Http/Controllers/PaymentController.php"])
    )
    state = make_state()

    with pytest.raises(ScopeViolation, match="denylisted"):
        locate(state, client, repo_dir)


def test_locate_raises_on_hallucinated_path(repo_dir):
    client = fake_claude_client(json.dumps(["app/Http/Controllers/DoesNotExist.php"]))
    state = make_state()

    with pytest.raises(ScopeViolation, match="not a tracked file"):
        locate(state, client, repo_dir)


def test_locate_raises_on_empty_list(repo_dir):
    client = fake_claude_client(json.dumps([]))
    state = make_state()

    with pytest.raises(ScopeViolation, match="zero file targets"):
        locate(state, client, repo_dir)


def test_locate_raises_on_invalid_json(repo_dir):
    client = fake_claude_client("not json at all")
    state = make_state()

    with pytest.raises(ScopeViolation, match="not valid JSON"):
        locate(state, client, repo_dir)


def test_locate_strips_markdown_code_fence(repo_dir):
    client = fake_claude_client(
        "```json\n" + json.dumps(["app/Http/Controllers/FinanceController.php"]) + "\n```"
    )
    state = make_state()

    result = locate(state, client, repo_dir)

    assert result.file_targets == ["app/Http/Controllers/FinanceController.php"]


def test_locate_rejects_whole_batch_if_any_target_is_denylisted(repo_dir):
    # A mix of one safe and one denylisted path must reject the whole
    # batch, not silently drop only the bad one.
    client = fake_claude_client(
        json.dumps(
            [
                "app/Http/Controllers/FinanceController.php",
                "app/Http/Controllers/PaymentController.php",
            ]
        )
    )
    state = make_state()

    with pytest.raises(ScopeViolation, match="denylisted"):
        locate(state, client, repo_dir)


def test_locate_rejects_symlinked_path(repo_dir):
    client = fake_claude_client(
        json.dumps(["app/Http/Controllers/FinanceController.php"])
    )
    state = make_state()

    with patch("nodes.locate.os.path.islink", return_value=True):
        with pytest.raises(ScopeViolation, match="symlink"):
            locate(state, client, repo_dir)


def test_locate_rejects_too_many_targets(repo_dir):
    # Only two files exist in the fixture repo, so this also exercises the
    # hallucination guard incidentally -- use MAX_FILE_TARGETS+1 copies of
    # a real path is not meaningful (dupes), so assert on the cap directly
    # via a monkeypatched, smaller cap instead of needing 11 real files.
    import nodes.locate as locate_module

    client = fake_claude_client(
        json.dumps(["app/Http/Controllers/FinanceController.php"] * 2)
    )
    state = make_state()

    with patch.object(locate_module, "MAX_FILE_TARGETS", 1):
        with pytest.raises(ScopeViolation, match="exceeding the cap"):
            locate(state, client, repo_dir)


def test_locate_wraps_claude_failure(repo_dir):
    client = MagicMock()
    client.complete.side_effect = RuntimeError("network error")
    state = make_state()

    with pytest.raises(ScopeViolation, match="Claude call failed"):
        locate(state, client, repo_dir)
