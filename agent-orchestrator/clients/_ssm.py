"""Shared SSM secret-fetch helper for the two client wrappers. Not a public
API in its own right -- ClaudeClient and GitHubClient both need to read one
SecureString parameter at construction time and this avoids duplicating
that boto3 call and its error handling in two places."""

import boto3
from botocore.exceptions import ClientError


def fetch_ssm_secret(param_name: str) -> str:
    ssm = boto3.client("ssm")
    try:
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
    except ClientError as exc:
        raise RuntimeError(
            f"Could not fetch SSM parameter {param_name}: {exc}"
        ) from exc
    return resp["Parameter"]["Value"]
