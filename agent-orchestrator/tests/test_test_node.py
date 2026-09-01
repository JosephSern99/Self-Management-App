import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from nodes.test import TestsFailedAfterRetries, run_tests
from nodes.test import test_and_retry as run_test_and_retry
from state import RunState


def make_state():
    return RunState(
        run_id="test-run",
        ticket={"number": 1, "title": "t", "body": "b"},
        plan="fix it",
        file_targets=["app/Foo.php"],
    )


def fake_completed(returncode, stdout="", stderr=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def test_run_tests_forces_isolated_env(tmp_path):
    with patch("nodes.test.subprocess.run", return_value=fake_completed(0)) as mock_run:
        run_tests(str(tmp_path))

    called_env = mock_run.call_args.kwargs["env"]
    assert called_env["DB_CONNECTION"] == "mysql"
    assert called_env["DB_DATABASE"] == "agent_orchestrator_test"
    assert called_env["APP_URL"] == "http://localhost"


def test_run_tests_reports_pass():
    with patch("nodes.test.subprocess.run", return_value=fake_completed(0, stdout="OK")):
        result = run_tests("/fake/repo")
    assert result["passed"] is True


def test_run_tests_reports_fail():
    with patch(
        "nodes.test.subprocess.run",
        return_value=fake_completed(1, stdout="", stderr="FAILED"),
    ):
        result = run_tests("/fake/repo")
    assert result["passed"] is False
    assert "FAILED" in result["output"]


def test_run_tests_forced_env_wins_over_conflicting_parent_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_HOST", "some-real-production-host")
    with patch("nodes.test.subprocess.run", return_value=fake_completed(0)) as mock_run:
        run_tests(str(tmp_path))

    called_env = mock_run.call_args.kwargs["env"]
    assert called_env["DB_HOST"] == "127.0.0.1"


def test_run_tests_handles_php_not_found():
    with patch("nodes.test.subprocess.run", side_effect=FileNotFoundError("php not found")):
        result = run_tests("/fake/repo")
    assert result["passed"] is False
    assert "php" in result["output"].lower()


def test_run_tests_handles_timeout():
    with patch(
        "nodes.test.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="php artisan test", timeout=300),
    ):
        result = run_tests("/fake/repo")
    assert result["passed"] is False
    assert "timed out" in result["output"].lower()


def test_and_retry_returns_immediately_on_first_pass():
    state = make_state()
    claude_client = MagicMock()

    with patch("nodes.test.run_tests", return_value={"passed": True, "output": "", "returncode": 0}):
        result = run_test_and_retry(state, claude_client, "/fake/repo")

    assert result.test_result["passed"] is True
    claude_client.complete.assert_not_called()  # implement() never re-invoked


def test_and_retry_retries_implement_on_failure_then_succeeds():
    state = make_state()
    claude_client = MagicMock()

    results = [
        {"passed": False, "output": "fail 1", "returncode": 1},
        {"passed": True, "output": "", "returncode": 0},
    ]

    with patch("nodes.test.run_tests", side_effect=results), patch(
        "nodes.test.implement", return_value=state
    ) as mock_implement:
        result = run_test_and_retry(state, claude_client, "/fake/repo")

    assert result.test_result["passed"] is True
    mock_implement.assert_called_once()
    assert mock_implement.call_args.kwargs["feedback"] == "fail 1"


def test_and_retry_each_retry_gets_that_attempts_own_feedback_not_stale():
    # 3 distinct failures across attempts; each implement() retry must see
    # THAT attempt's own output, not attempt 1's reused for every retry.
    state = make_state()
    claude_client = MagicMock()

    results = [
        {"passed": False, "output": "fail 1", "returncode": 1},
        {"passed": False, "output": "fail 2", "returncode": 1},
        {"passed": True, "output": "", "returncode": 0},
    ]

    with patch("nodes.test.run_tests", side_effect=results), patch(
        "nodes.test.implement", return_value=state
    ) as mock_implement:
        result = run_test_and_retry(state, claude_client, "/fake/repo", max_attempts=3)

    assert result.test_result["passed"] is True
    assert mock_implement.call_count == 2
    assert mock_implement.call_args_list[0].kwargs["feedback"] == "fail 1"
    assert mock_implement.call_args_list[1].kwargs["feedback"] == "fail 2"


def test_and_retry_raises_if_implement_itself_fails_during_retry():
    state = make_state()
    claude_client = MagicMock()

    with patch(
        "nodes.test.run_tests",
        return_value={"passed": False, "output": "fail 1", "returncode": 1},
    ), patch("nodes.test.implement", side_effect=RuntimeError("disk full")):
        with pytest.raises(TestsFailedAfterRetries, match="disk full"):
            run_test_and_retry(state, claude_client, "/fake/repo")


def test_and_retry_rejects_max_attempts_below_one():
    state = make_state()
    claude_client = MagicMock()

    with pytest.raises(ValueError, match="max_attempts must be"):
        run_test_and_retry(state, claude_client, "/fake/repo", max_attempts=0)


def test_and_retry_raises_after_max_attempts():
    state = make_state()
    claude_client = MagicMock()

    always_fails = {"passed": False, "output": "still broken", "returncode": 1}

    with patch("nodes.test.run_tests", return_value=always_fails), patch(
        "nodes.test.implement", return_value=state
    ) as mock_implement:
        with pytest.raises(TestsFailedAfterRetries, match="still broken"):
            run_test_and_retry(state, claude_client, "/fake/repo")

    # 3 total test attempts, 2 retries (implement called twice more after
    # the initial attempt the caller is assumed to have already made).
    assert mock_implement.call_count == 2
