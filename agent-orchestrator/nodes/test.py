"""Test node: runs php artisan test against an isolated database and URL,
never the repo's real .env values (Architecture AD-2). Owns the
implement-then-test retry loop: assumes Implement has already run once,
retries it up to 2 more times on failure before raising.

Isolation uses a local MariaDB database (agent_orchestrator_test), not
SQLite: AL2023 has no pdo_sqlite package for any PHP version and PECL
compilation fails against PHP 8.1's Zend API (verified live). MariaDB is
provisioned once at first boot (provision_trigger_infra.py) alongside PHP.
"""

import logging
import os
import subprocess

from clients.claude_client import ClaudeClient
from nodes.implement import implement
from state import RunState

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3  # 1 initial Implement (by the caller) + up to 2 retries
TEST_TIMEOUT_SECONDS = 300
OUTPUT_CHAR_LIMIT = 4000  # keeps retry-feedback prompts and stored state bounded

# Forced regardless of the repo's real .env -- DB isolation is AD-2's
# explicit requirement (amended to MariaDB -- see module docstring);
# APP_URL is forced defensively after investigation showed a misconfigured
# value (e.g. a subpath, as some local dev setups use) makes Laravel's HTTP
# test client silently mismatch nearly every route, producing false
# failures that would burn Claude spend retrying a problem that has
# nothing to do with the actual code change.
FORCED_TEST_ENV = {
    "DB_CONNECTION": "mysql",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
    "DB_DATABASE": "agent_orchestrator_test",
    # Not `root`: MariaDB's root defaults to unix_socket auth, which
    # rejects any TCP connection regardless of password. A dedicated user
    # (provisioned in provision_trigger_infra.py) sidesteps that -- this
    # isn't a secret worth protecting, it only ever holds throwaway test
    # data on localhost.
    "DB_USERNAME": "agent_orchestrator",
    "DB_PASSWORD": "agent_test_db_pw",
    "APP_URL": "http://localhost",
    # The working copy has no .env at all (gitignored, never committed) --
    # Laravel requires APP_KEY regardless of testing context. A fixed test
    # key is fine here: it only ever encrypts throwaway session/cookie data
    # during a test run, never anything real.
    "APP_KEY": "base64:EsoUpkeWj9neryInaVV+PLkf38/iPjBdIdo5kEFQfYI=",
}


def _truncate(text: str, limit: int = OUTPUT_CHAR_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"...[truncated, showing last {limit} chars]...\n" + text[-limit:]


def run_tests(repo_dir: str) -> dict:
    env = {**os.environ, **FORCED_TEST_ENV}

    # Defensive: cached config would bake in the real .env's DB/URL values,
    # silently defeating the env-var overrides above. The repo has no
    # config cache committed today, but this costs nothing if there's
    # nothing to clear. Best-effort only -- a failure here isn't itself a
    # test failure, and the real php-availability check happens below.
    try:
        subprocess.run(
            ["php", "artisan", "config:clear"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["php", "artisan", "test"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.error("php artisan test exceeded %ss timeout; treating as failed.", TEST_TIMEOUT_SECONDS)
        return {
            "passed": False,
            "output": f"Test run timed out after {TEST_TIMEOUT_SECONDS}s.",
            "returncode": None,
        }
    except (FileNotFoundError, OSError) as exc:
        logger.error("Could not start php artisan test: %s", exc)
        return {"passed": False, "output": f"Could not run php: {exc}", "returncode": None}

    output = _truncate(result.stdout + result.stderr)
    passed = result.returncode == 0
    logger.info("Test run: %s (exit %s)", "PASSED" if passed else "FAILED", result.returncode)
    return {"passed": passed, "output": output, "returncode": result.returncode}


class TestsFailedAfterRetries(RuntimeError):
    pass


def test_and_retry(
    state: RunState,
    claude_client: ClaudeClient,
    repo_dir: str,
    max_attempts: int = MAX_ATTEMPTS,
) -> RunState:
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    for attempt in range(1, max_attempts + 1):
        result = run_tests(repo_dir)
        state.test_result = result

        if result["passed"]:
            return state

        if attempt < max_attempts:
            logger.warning(
                "Test attempt %s/%s failed, retrying Implement with failure feedback.",
                attempt,
                max_attempts,
            )
            try:
                state = implement(state, claude_client, repo_dir, feedback=result["output"])
            except Exception as exc:
                logger.error("Implement retry %s failed: %s", attempt, exc)
                raise TestsFailedAfterRetries(
                    f"Implement retry {attempt} failed before tests could run "
                    f"again: {exc}"
                ) from exc
        else:
            raise TestsFailedAfterRetries(
                f"Tests still failing after {max_attempts} attempts. Last output:\n"
                f"{result['output']}"
            )

    return state
