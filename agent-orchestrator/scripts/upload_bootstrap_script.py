"""Idempotently uploads bootstrap/run.sh to the Run Log bucket at
bootstrap/run.sh, where Story 1.2's EC2 instance fetches and executes it on
every boot. Re-run any time run.sh changes.

Usage:
    python agent-orchestrator/scripts/upload_bootstrap_script.py
"""

import subprocess
import sys
from pathlib import Path

import boto3

BOOTSTRAP_S3_KEY = "bootstrap/run.sh"
LOCAL_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "bootstrap" / "run.sh"


def require_aws_credentials() -> str:
    try:
        sts = boto3.client("sts")
        return sts.get_caller_identity()["Account"]
    except Exception as exc:
        print(
            "ERROR: no usable AWS credentials found. Run `aws configure` "
            f"and re-run this script.\nDetail: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    account_id = require_aws_credentials()
    bucket_name = f"{account_id}-agent-orchestrator-run-logs"

    if not LOCAL_SCRIPT_PATH.is_file():
        print(f"ERROR: {LOCAL_SCRIPT_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    script_bytes = LOCAL_SCRIPT_PATH.read_bytes()
    if b"\r\n" in script_bytes:
        print(
            f"ERROR: {LOCAL_SCRIPT_PATH.name} has CRLF line endings, which "
            "break on the Linux EC2 instance. Save it with LF endings.",
            file=sys.stderr,
        )
        sys.exit(1)
    lint = subprocess.run(
        ["bash", "-n"], input=script_bytes, capture_output=True, text=False
    )
    if lint.returncode != 0:
        print(
            f"ERROR: {LOCAL_SCRIPT_PATH.name} fails `bash -n` syntax check, "
            f"not uploading:\n{lint.stderr.decode(errors='replace')}",
            file=sys.stderr,
        )
        sys.exit(1)

    s3 = boto3.client("s3")
    try:
        s3.upload_file(
            str(LOCAL_SCRIPT_PATH),
            bucket_name,
            BOOTSTRAP_S3_KEY,
            ExtraArgs={"ContentType": "text/x-shellscript"},
        )
    except Exception as exc:
        print(
            f"ERROR: upload failed: {exc}\n"
            "Re-running this script after fixing the issue is safe.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Uploaded {LOCAL_SCRIPT_PATH.name} -> s3://{bucket_name}/{BOOTSTRAP_S3_KEY}")


if __name__ == "__main__":
    main()
