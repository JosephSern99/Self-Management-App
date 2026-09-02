from unittest.mock import MagicMock, patch

import pytest

from denylist import ScopeViolation
from nodes.push import push
from state import RunState


def fake_completed(stdout=""):
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


def make_state(diff="--- a/foo\n+++ b/foo\n", review_verdict="PASS"):
    return RunState(
        run_id="test-run",
        ticket={"number": 42, "title": "Fix the thing", "body": "b"},
        plan="do the thing",
        diff=diff,
        test_result={"passed": True, "output": "OK"},
        review_verdict=review_verdict,
    )


def test_push_clean_commits_pushes_and_closes_issue(tmp_path):
    github_client = MagicMock()
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Foo.php\n"),
    ):
        result = push(state, github_client, str(tmp_path))

    assert result is state
    github_client.push.assert_called_once()
    call = github_client.push.call_args
    assert call.args[0] == str(tmp_path)
    assert call.kwargs["paths"] == ["app/Foo.php"]

    github_client.comment_issue.assert_called_once()
    comment_args = github_client.comment_issue.call_args.args
    assert comment_args[0] == 42
    comment_body = comment_args[1]
    assert "do the thing" in comment_body  # state.plan
    assert "passed" in comment_body  # derived from state.test_result
    assert "PASS" in comment_body  # state.review_verdict
    github_client.close_issue.assert_called_once_with(42)


def test_push_detects_untracked_new_file(tmp_path):
    # git diff --name-only alone misses brand-new files Implement created;
    # _diffed_files must catch untracked ("??") entries too.
    github_client = MagicMock()
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed("?? app/NewFile.php\n"),
    ):
        push(state, github_client, str(tmp_path))

    assert github_client.push.call_args.kwargs["paths"] == ["app/NewFile.php"]


def test_push_detects_untracked_denylisted_file(tmp_path):
    github_client = MagicMock()
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed("?? composer.json\n"),
    ):
        with pytest.raises(ScopeViolation, match="denylisted"):
            push(state, github_client, str(tmp_path))

    github_client.push.assert_not_called()


def test_push_blocked_by_denylisted_drift(tmp_path):
    github_client = MagicMock()
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Http/Controllers/PaymentController.php\n"),
    ):
        with pytest.raises(ScopeViolation, match="denylisted"):
            push(state, github_client, str(tmp_path))

    github_client.push.assert_not_called()
    github_client.comment_issue.assert_not_called()
    github_client.close_issue.assert_not_called()


def test_push_blocked_by_denylist_among_multiple_files(tmp_path):
    github_client = MagicMock()
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Foo.php\n M composer.json\n"),
    ):
        with pytest.raises(ScopeViolation):
            push(state, github_client, str(tmp_path))

    github_client.push.assert_not_called()


def test_push_raises_on_empty_diff_before_touching_git(tmp_path):
    github_client = MagicMock()
    state = make_state(diff="")

    with patch("nodes.push.subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="diff is empty"):
            push(state, github_client, str(tmp_path))

    mock_run.assert_not_called()
    github_client.push.assert_not_called()


def test_push_raises_if_git_reports_no_changed_files(tmp_path):
    github_client = MagicMock()
    state = make_state()

    with patch("nodes.push.subprocess.run", return_value=fake_completed("")):
        with pytest.raises(ValueError, match="no changed files"):
            push(state, github_client, str(tmp_path))

    github_client.push.assert_not_called()


def test_push_never_uses_file_targets_from_locate(tmp_path):
    # state.file_targets is what Locate planned; push must re-derive from
    # git, not trust it -- simulate drift where the plan and the real diff
    # disagree.
    github_client = MagicMock()
    state = make_state()
    state.file_targets = ["app/Foo.php"]

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Bar.php\n"),
    ):
        push(state, github_client, str(tmp_path))

    assert github_client.push.call_args.kwargs["paths"] == ["app/Bar.php"]


def test_push_raises_if_review_verdict_is_fail(tmp_path):
    github_client = MagicMock()
    state = make_state(review_verdict="FAIL: diff doesn't match plan")

    with patch("nodes.push.subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="self-review did not pass"):
            push(state, github_client, str(tmp_path))

    mock_run.assert_not_called()
    github_client.push.assert_not_called()


def test_push_does_not_raise_when_comment_issue_fails_after_successful_push(tmp_path):
    # The git push to main already irreversibly succeeded by the time
    # comment_issue/close_issue run -- a failure there must not make push()
    # raise, since orchestrator.py would otherwise post a false "no changes
    # were made" failure comment on top of a change that's already live.
    github_client = MagicMock()
    github_client.comment_issue.side_effect = RuntimeError("GitHub API hiccup")
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Foo.php\n"),
    ):
        result = push(state, github_client, str(tmp_path))

    assert result is state
    github_client.push.assert_called_once()
    github_client.comment_issue.assert_called_once()
    # close_issue is still attempted even though comment_issue raised.
    github_client.close_issue.assert_called_once_with(42)


def test_push_does_not_raise_when_close_issue_fails_after_successful_push(tmp_path):
    github_client = MagicMock()
    github_client.close_issue.side_effect = RuntimeError("GitHub API hiccup")
    state = make_state()

    with patch(
        "nodes.push.subprocess.run",
        return_value=fake_completed(" M app/Foo.php\n"),
    ):
        result = push(state, github_client, str(tmp_path))

    assert result is state
    github_client.push.assert_called_once()
    github_client.comment_issue.assert_called_once()
    github_client.close_issue.assert_called_once_with(42)


def test_push_raises_if_review_verdict_is_empty(tmp_path):
    github_client = MagicMock()
    state = make_state(review_verdict="")

    with patch("nodes.push.subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="self-review did not pass"):
            push(state, github_client, str(tmp_path))

    mock_run.assert_not_called()
    github_client.push.assert_not_called()
