"""Idempotently provision the SSM secrets and S3 Run Log bucket the agent
orchestrator depends on. Reads secret values from GITHUB_PAT / CLAUDE_API_KEY
env vars, falling back to an interactive getpass prompt. Never accepts a
secret as a CLI argument and never writes one to disk.

Usage:
    python agent-orchestrator/scripts/provision_secrets_storage.py
"""

import getpass
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

GITHUB_PAT_PARAM = "/agent-orchestrator/github-pat"
CLAUDE_API_KEY_PARAM = "/agent-orchestrator/claude-api-key"


def require_aws_credentials() -> str:
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return identity["Account"]
    except Exception as exc:
        print(
            "ERROR: no usable AWS credentials found. Run `aws configure` "
            "with an IAM user that has permission to create SSM parameters "
            f"and S3 buckets, then re-run this script.\nDetail: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_secret(env_var_name: str, prompt_label: str) -> str:
    value = os.environ.get(env_var_name, "").strip()
    if value:
        return value
    value = getpass.getpass(f"{prompt_label} (input hidden): ").strip()
    if not value:
        print(
            f"ERROR: no value supplied for {prompt_label}. Set the "
            f"{env_var_name} env var or paste it at the prompt.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def put_secure_parameter(ssm_client, name: str, value: str) -> None:
    ssm_client.put_parameter(
        Name=name,
        Value=value,
        Type="SecureString",
        Overwrite=True,
        Tier="Standard",
    )
    print(f"  SSM parameter ready: {name}")


def ensure_run_log_bucket(s3_client, bucket_name: str, region: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"  S3 bucket already exists: {bucket_name}")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "403":
            print(
                f"ERROR: bucket name '{bucket_name}' already exists and is "
                "owned by a different AWS account. S3 bucket names are "
                "globally unique -- this should not normally happen since "
                "the name is derived from this account's own id.",
                file=sys.stderr,
            )
            sys.exit(1)
        if error_code not in ("404", "NoSuchBucket"):
            raise
        create_kwargs = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": region
            }
        try:
            s3_client.create_bucket(**create_kwargs)
            print(f"  S3 bucket created: {bucket_name}")
        except ClientError as create_exc:
            create_error_code = create_exc.response.get("Error", {}).get(
                "Code", ""
            )
            if create_error_code == "BucketAlreadyOwnedByYou":
                print(f"  S3 bucket already exists: {bucket_name}")
            else:
                raise

    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    s3_client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        },
    )

    tls_only_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    }
    s3_client.put_bucket_policy(
        Bucket=bucket_name, Policy=json.dumps(tls_only_policy)
    )
    print(
        "  Public access blocked, default encryption and TLS-only policy applied"
    )


def main() -> None:
    account_id = require_aws_credentials()

    session = boto3.session.Session()
    region = session.region_name
    if not region:
        print(
            "ERROR: no default region configured. Run `aws configure` and "
            "set a default region.",
            file=sys.stderr,
        )
        sys.exit(1)

    github_pat = get_secret("GITHUB_PAT", "GitHub PAT")
    claude_api_key = get_secret("CLAUDE_API_KEY", "Claude API key")

    ssm = session.client("ssm")
    s3 = session.client("s3")

    try:
        print("Provisioning SSM parameters...")
        put_secure_parameter(ssm, GITHUB_PAT_PARAM, github_pat)
        put_secure_parameter(ssm, CLAUDE_API_KEY_PARAM, claude_api_key)

        bucket_name = f"{account_id}-agent-orchestrator-run-logs"
        print("Provisioning S3 Run Log bucket...")
        ensure_run_log_bucket(s3, bucket_name, region)
    except ClientError as exc:
        print(
            f"ERROR: AWS rejected a provisioning call: {exc}\n"
            "Nothing further will be attempted. Re-running this script "
            "after fixing the underlying issue (e.g. permissions) is safe "
            "-- it will pick up wherever it left off.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nDone.")
    print(f"  SSM: {GITHUB_PAT_PARAM}")
    print(f"  SSM: {CLAUDE_API_KEY_PARAM}")
    print(f"  S3 bucket: {bucket_name}")


if __name__ == "__main__":
    main()
