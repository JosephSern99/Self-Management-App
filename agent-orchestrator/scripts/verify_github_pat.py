"""One-off sanity check: confirms the GitHub PAT stored in SSM is valid and
has the access this project needs. Never prints the token itself.

Usage:
    python agent-orchestrator/scripts/verify_github_pat.py
"""

import sys

import boto3
import urllib.request
import urllib.error
import json

GITHUB_PAT_PARAM = "/agent-orchestrator/github-pat"
REPO = "self-management-app"


def get_pat() -> str:
    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=GITHUB_PAT_PARAM, WithDecryption=True)
    return resp["Parameter"]["Value"]


def github_get(path: str, token: str):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), dict(e.headers)


def main() -> None:
    token = get_pat()

    status, body, headers = github_get("/user", token)
    if status == 401:
        print("FAIL: token is invalid or expired (401 from /user).")
        sys.exit(1)

    scopes = headers.get("X-OAuth-Scopes", "") or headers.get(
        "X-Accepted-OAuth-Scopes", ""
    )
    print(f"Authenticated as: {body.get('login', '(no login on fine-grained token)')}")

    # Find the target repo by listing repos this token can see (works for
    # both classic and fine-grained tokens without needing the owner login).
    status, repos_body, _ = github_get("/user/repos?per_page=100", token)
    if status != 200:
        print(f"FAIL: could not list accessible repos (status {status}): {repos_body}")
        sys.exit(1)

    match = next(
        (r for r in repos_body if r["name"].lower() == REPO.lower()), None
    )
    if not match:
        print(
            f"FAIL: token cannot see a repo named '{REPO}'. Check the "
            "fine-grained token's repository access includes this repo."
        )
        sys.exit(1)

    permissions = match.get("permissions", {})
    print(f"Found repo: {match['full_name']}")
    print(f"  push permission: {permissions.get('push')}")
    print(f"  admin permission: {permissions.get('admin')}")

    status, issues_body, _ = github_get(f"/repos/{match['full_name']}/issues?per_page=1", token)
    if status == 200:
        print("  can read issues: True")
    else:
        print(f"  can read issues: False (status {status})")

    if not permissions.get("push"):
        print(
            "\nWARNING: token does not have push access to this repo. "
            "Push node (Story 1.7) will fail. Re-check the fine-grained "
            "token's 'Contents: Read and write' permission."
        )
        sys.exit(1)

    print("\nPASS: token is valid and has the access this project needs.")


if __name__ == "__main__":
    main()
