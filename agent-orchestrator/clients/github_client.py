"""The single wrapper around GitHub interactions the orchestrator's nodes
need: reading/commenting/closing an issue, and pushing the finished commit.
Architecture AD-6 -- nodes call this, never the raw API/git directly.

Note: this is separate from trigger_lambda/handler.py's own inline GitHub
calls, which are Lambda-specific (label-claim logic that runs before any
node exists) and intentionally not refactored to share this module.
"""

import json
import logging
import subprocess
import urllib.error
import urllib.request

from clients._ssm import fetch_ssm_secret

logger = logging.getLogger(__name__)

GITHUB_PAT_PARAM = "/agent-orchestrator/github-pat"
REPO_OWNER = "JosephSern99"
REPO_NAME = "Self-Management-App"
REPO_HOST_PATH = f"github.com/{REPO_OWNER}/{REPO_NAME}.git"
REQUEST_TIMEOUT_SECONDS = 15


class GitHubRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status, body):
        super().__init__(f"GitHub {method} {path} failed: {status} {body}")
        self.status = status
        self.body = body


class GitPushError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or fetch_ssm_secret(GITHUB_PAT_PARAM)

    def _sanitize(self, value: object) -> str:
        """Redacts self.token out of an exception's (or any object's)
        string representation before it's embedded into a raised message --
        subprocess.CalledProcessError's str() includes the full command
        argv, which for the credentialed set-url/push commands contains the
        raw PAT-embedded URL. Without this, a failure here could leak the
        live GitHub PAT into a persisted RunLog or a public issue comment."""
        text = str(value)
        if self.token:
            text = text.replace(self.token, "REDACTED")
        return text

    def _request(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read()
                try:
                    parsed = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    parsed = raw.decode(errors="replace")
                return resp.status, parsed
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw.decode(errors="replace")
            raise GitHubRequestError(method, path, e.code, parsed) from e
        except urllib.error.URLError as e:
            raise GitHubRequestError(method, path, None, str(e)) from e

    def get_issue(self, issue_number: int) -> dict:
        _, body = self._request(
            "GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
        )
        return body

    def comment_issue(self, issue_number: int, body: str) -> dict:
        _, resp = self._request(
            "POST",
            f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments",
            body={"body": body},
        )
        return resp

    def close_issue(self, issue_number: int) -> dict:
        _, resp = self._request(
            "PATCH",
            f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}",
            body={"state": "closed"},
        )
        return resp

    def push(
        self, repo_dir: str, commit_message: str, paths: list[str] | None = None
    ) -> str:
        """Stages (all changes, or just `paths` if given), commits, and
        pushes `main`. The PAT is only placed in the remote URL for the
        push itself, then scrubbed back to a credential-less URL -- same
        pattern as bootstrap/run.sh, so the token never sits in
        .git/config at rest. Raises GitPushError on any failure, with the
        original cause preserved even if the URL-cleanup step also fails."""
        subprocess.run(
            ["git", "-C", repo_dir, "add"] + (paths if paths else ["-A"]),
            check=True,
        )

        status = subprocess.run(
            ["git", "-C", repo_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        if not status.stdout.strip():
            logger.info("Nothing to commit; working copy already matches HEAD.")
        else:
            subprocess.run(
                ["git", "-C", repo_dir, "commit", "-m", commit_message], check=True
            )

        branch = subprocess.run(
            ["git", "-C", repo_dir, "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if branch != "main":
            raise GitPushError(
                f"Refusing to push: working copy is on branch '{branch}', not 'main'."
            )

        credentialed_url = f"https://x-access-token:{self.token}@{REPO_HOST_PATH}"
        clean_url = f"https://{REPO_HOST_PATH}"
        push_error = None
        try:
            subprocess.run(
                ["git", "-C", repo_dir, "remote", "set-url", "origin", credentialed_url],
                check=True,
            )
            subprocess.run(["git", "-C", repo_dir, "push", "origin", "main"], check=True)
        except subprocess.CalledProcessError as exc:
            push_error = exc
        finally:
            try:
                subprocess.run(
                    ["git", "-C", repo_dir, "remote", "set-url", "origin", clean_url],
                    check=True,
                )
            except subprocess.CalledProcessError as cleanup_exc:
                if push_error:
                    raise GitPushError(
                        f"Push failed ({self._sanitize(push_error)}) AND credential "
                        f"cleanup also failed ({self._sanitize(cleanup_exc)}) -- the "
                        f"PAT may still be in {repo_dir}/.git/config."
                    ) from push_error
                logger.error(
                    "Push succeeded but credential cleanup failed: %s. PAT may "
                    "still be in %s/.git/config.",
                    self._sanitize(cleanup_exc),
                    repo_dir,
                )

        if push_error:
            raise GitPushError(f"git push failed: {self._sanitize(push_error)}") from push_error

        rev = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return rev.stdout.strip()
