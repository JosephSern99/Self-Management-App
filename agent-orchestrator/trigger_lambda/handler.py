"""EventBridge-scheduled Lambda: finds the oldest open GitHub issue labeled
`agent-ready` on the target repo, atomically claims it (label swap to
`agent-processing`), tags the EC2 orchestrator instance with the issue
number, and starts it. No-op if a Run is already in progress or no
matching issue exists. Any partial failure rolls the label back to
`agent-ready` so the same issue is retried on the next poll rather than
getting stuck. Stdlib + boto3 only -- no dependency layer needed.
"""

import json
import logging
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_PAT_PARAM = "/agent-orchestrator/github-pat"
EC2_INSTANCE_ID_PARAM = "/agent-orchestrator/ec2-instance-id"
REPO_OWNER = "JosephSern99"
REPO_NAME = "Self-Management-App"
TICKET_LABEL = "agent-ready"
CLAIMED_LABEL = "agent-processing"
ISSUE_TAG_KEY = "CurrentIssueNumber"
ACTIVE_INSTANCE_STATES = ("running", "pending", "stopping", "shutting-down")


def get_ssm_value(name: str, with_decryption: bool = False) -> str:
    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return resp["Parameter"]["Value"]


def github_request(method: str, path: str, token: str, body=None):
    """Returns (status, json_body). status is None on a transport-level
    failure (timeout, DNS, connection reset, malformed response) -- callers
    must treat None the same as a hard failure, never iterate the body."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error("GitHub request transport failure: %s %s -- %s", method, path, e)
        return None, None


def find_oldest_ready_issue(token: str):
    status, issues = github_request(
        "GET",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/issues"
        f"?labels={TICKET_LABEL}&state=open&sort=created&direction=asc&per_page=100",
        token,
    )
    if status != 200 or not issues:
        if status != 200:
            logger.error("GitHub issue list failed: %s %s", status, issues)
        return None
    # The issues endpoint also returns pull requests; exclude those.
    candidates = [i for i in issues if "pull_request" not in i]
    if not candidates:
        return None
    return min(candidates, key=lambda i: i["number"])


def add_label(issue_number: int, label: str, token: str) -> bool:
    status, _ = github_request(
        "POST",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/labels",
        token,
        body={"labels": [label]},
    )
    return status in (200, 201)


def remove_label(issue_number: int, label: str, token: str) -> bool:
    status, _ = github_request(
        "DELETE",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/labels/{label}",
        token,
    )
    # 404 just means the label was already gone -- not a failure.
    return status in (200, 404)


def claim_issue(issue_number: int, token: str) -> bool:
    """Swaps agent-ready -> agent-processing. On any failure, rolls back
    whatever half of the swap already happened so the issue ends up back in
    a clean, retryable state -- never half-claimed."""
    if not add_label(issue_number, CLAIMED_LABEL, token):
        logger.error("Failed to add claimed label to #%s", issue_number)
        return False

    if not remove_label(issue_number, TICKET_LABEL, token):
        logger.error(
            "Failed to remove %s label from #%s; rolling back claim.",
            TICKET_LABEL,
            issue_number,
        )
        remove_label(issue_number, CLAIMED_LABEL, token)
        return False

    return True


def release_claim(issue_number: int, token: str) -> None:
    """Best-effort rollback: restores agent-ready and removes
    agent-processing so a downstream AWS failure doesn't strand the issue."""
    add_label(issue_number, TICKET_LABEL, token)
    remove_label(issue_number, CLAIMED_LABEL, token)


def instance_is_running(ec2_client, instance_id: str) -> bool:
    resp = ec2_client.describe_instances(InstanceIds=[instance_id])
    reservations = resp.get("Reservations") or []
    if not reservations or not reservations[0].get("Instances"):
        logger.error("Instance %s not found in describe_instances response.", instance_id)
        return False
    state = reservations[0]["Instances"][0]["State"]["Name"]
    return state in ACTIVE_INSTANCE_STATES


def handler(event, context):
    token = get_ssm_value(GITHUB_PAT_PARAM, with_decryption=True)
    instance_id = get_ssm_value(EC2_INSTANCE_ID_PARAM)

    ec2 = boto3.client("ec2")

    if instance_is_running(ec2, instance_id):
        logger.info("Run already in progress, skipping.")
        return {"action": "skipped", "reason": "instance already running"}

    issue = find_oldest_ready_issue(token)
    if not issue:
        logger.info("No ticket found.")
        return {"action": "skipped", "reason": "no matching issue"}

    issue_number = issue["number"]

    if not claim_issue(issue_number, token):
        logger.error("Could not claim issue #%s; leaving instance stopped.", issue_number)
        return {"action": "failed", "reason": "label claim failed", "issue": issue_number}

    try:
        ec2.create_tags(
            Resources=[instance_id],
            Tags=[{"Key": ISSUE_TAG_KEY, "Value": str(issue_number)}],
        )
        ec2.start_instances(InstanceIds=[instance_id])
    except ClientError as exc:
        logger.error(
            "AWS failure starting instance for #%s: %s -- releasing claim.",
            issue_number,
            exc,
        )
        release_claim(issue_number, token)
        return {"action": "failed", "reason": "aws start failed", "issue": issue_number}

    logger.info("Started instance %s for issue #%s.", instance_id, issue_number)
    return {"action": "started", "issue": issue_number, "instance_id": instance_id}
