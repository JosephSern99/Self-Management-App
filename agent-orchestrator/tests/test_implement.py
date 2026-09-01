from unittest.mock import MagicMock

import pytest

from denylist import ScopeViolation
from nodes.implement import implement
from state import RunState


def fake_claude_client(response_text: str = "<?php\n// new content\n"):
    client = MagicMock()
    client.complete.return_value = response_text
    return client


def make_state(file_targets):
    return RunState(
        run_id="test-run",
        ticket={"number": 1, "title": "t", "body": "b"},
        plan="do the thing",
        file_targets=file_targets,
    )


def test_implement_writes_target_file(tmp_path):
    target_dir = tmp_path / "app"
    target_dir.mkdir()
    target_file = target_dir / "Foo.php"
    target_file.write_text("<?php\n// old content\n")

    client = fake_claude_client("<?php\n// new content\n")
    state = make_state(["app/Foo.php"])

    result = implement(state, client, str(tmp_path))

    assert target_file.read_text() == "<?php\n// new content\n"
    assert result is state


def test_implement_never_writes_outside_file_targets(tmp_path):
    target_dir = tmp_path / "app"
    target_dir.mkdir()
    (target_dir / "Foo.php").write_text("<?php\n")

    client = fake_claude_client()
    state = make_state(["app/Foo.php"])

    implement(state, client, str(tmp_path))

    # Only the file in file_targets should exist -- nothing else created.
    all_files = list(tmp_path.rglob("*.php"))
    assert all_files == [target_dir / "Foo.php"]


def test_implement_creates_new_file_if_it_did_not_exist(tmp_path):
    client = fake_claude_client("<?php\n// brand new\n")
    state = make_state(["app/NewFile.php"])

    implement(state, client, str(tmp_path))

    written = tmp_path / "app" / "NewFile.php"
    assert written.exists()
    assert written.read_text() == "<?php\n// brand new\n"


def test_implement_strips_markdown_code_fence(tmp_path):
    client = fake_claude_client("```php\n<?php\n// fenced\n```")
    state = make_state(["app/Foo.php"])

    implement(state, client, str(tmp_path))

    written = (tmp_path / "app" / "Foo.php").read_text()
    assert written.strip() == "<?php\n// fenced"


def test_implement_raises_on_empty_file_targets(tmp_path):
    client = fake_claude_client()
    state = make_state([])

    with pytest.raises(ValueError, match="file_targets is empty"):
        implement(state, client, str(tmp_path))


def test_implement_includes_feedback_in_prompt_on_retry(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Foo.php").write_text("<?php\n")

    client = fake_claude_client()
    state = make_state(["app/Foo.php"])

    implement(state, client, str(tmp_path), feedback="TestFailure: assertion failed")

    sent_message = client.complete.call_args.kwargs["messages"][0]["content"]
    assert "TestFailure: assertion failed" in sent_message


def test_implement_rejects_path_traversal(tmp_path):
    client = fake_claude_client()
    state = make_state(["../../../../etc/passwd"])

    with pytest.raises(ScopeViolation, match="resolves outside"):
        implement(state, client, str(tmp_path))


def test_implement_rejects_absolute_path_outside_repo(tmp_path, tmp_path_factory):
    other_dir = tmp_path_factory.mktemp("outside")
    client = fake_claude_client()
    state = make_state([str(other_dir / "evil.php")])

    with pytest.raises(ScopeViolation, match="resolves outside"):
        implement(state, client, str(tmp_path))


def test_implement_rejects_denylisted_target_as_second_check(tmp_path):
    (tmp_path / "app" / "Http" / "Controllers").mkdir(parents=True)
    (tmp_path / "app" / "Http" / "Controllers" / "PaymentController.php").write_text("<?php\n")
    client = fake_claude_client()
    state = make_state(["app/Http/Controllers/PaymentController.php"])

    with pytest.raises(ScopeViolation, match="denylisted"):
        implement(state, client, str(tmp_path))


def test_implement_writes_top_level_file_without_directory_component(tmp_path):
    (tmp_path / "README.md").write_text("# old")
    client = fake_claude_client("# new")
    state = make_state(["README.md"])

    implement(state, client, str(tmp_path))  # must not raise FileNotFoundError

    assert (tmp_path / "README.md").read_text() == "# new"


def test_implement_raises_on_empty_claude_response(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Foo.php").write_text("<?php\n// original\n")
    client = fake_claude_client("   ")
    state = make_state(["app/Foo.php"])

    with pytest.raises(ScopeViolation, match="empty"):
        implement(state, client, str(tmp_path))

    # Original content must survive -- never truncate the file to nothing.
    assert (tmp_path / "app" / "Foo.php").read_text() == "<?php\n// original\n"


def test_implement_raises_on_truncated_code_fence(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Foo.php").write_text("<?php\n// original\n")
    client = fake_claude_client("```php\n<?php\n// half-written")
    state = make_state(["app/Foo.php"])

    with pytest.raises(ScopeViolation, match="truncated"):
        implement(state, client, str(tmp_path))


def test_implement_wraps_claude_failure(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Foo.php").write_text("<?php\n")
    client = MagicMock()
    client.complete.side_effect = RuntimeError("network error")
    state = make_state(["app/Foo.php"])

    with pytest.raises(RuntimeError, match="Implement's Claude call failed"):
        implement(state, client, str(tmp_path))


def test_implement_populates_diff(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Foo.php").write_text("<?php\n// old\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    client = fake_claude_client("<?php\n// new\n")
    state = make_state(["app/Foo.php"])

    result = implement(state, client, str(tmp_path))

    assert "old" in result.diff
    assert "new" in result.diff
