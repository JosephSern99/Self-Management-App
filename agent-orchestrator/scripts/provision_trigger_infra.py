"""Idempotently provision Story 1.2's trigger infrastructure: the EC2
orchestrator instance (stopped baseline, SSM-managed, no SSH), its IAM
role + security group, the trigger Lambda, and the EventBridge 5-minute
schedule that invokes it.

Usage:
    python agent-orchestrator/scripts/provision_trigger_infra.py
"""

import io
import json
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

EC2_INSTANCE_ID_PARAM = "/agent-orchestrator/ec2-instance-id"
AL2023_AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"

EC2_ROLE_NAME = "agent-orchestrator-ec2-role"
EC2_PROFILE_NAME = "agent-orchestrator-ec2-profile"
SG_NAME = "agent-orchestrator-sg"
LAMBDA_ROLE_NAME = "agent-orchestrator-lambda-role"
LAMBDA_FUNCTION_NAME = "agent-orchestrator-trigger"
EVENTBRIDGE_RULE_NAME = "agent-orchestrator-trigger-schedule"

HERE = Path(__file__).resolve().parent
HANDLER_PATH = HERE.parent / "trigger_lambda" / "handler.py"


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


def ensure_ec2_role(iam, bucket_name: str) -> str:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        iam.create_role(
            RoleName=EC2_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )
        print(f"  IAM role created: {EC2_ROLE_NAME}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"  IAM role already exists: {EC2_ROLE_NAME}")

    iam.attach_role_policy(
        RoleName=EC2_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    )

    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadOwnSecrets",
                "Effect": "Allow",
                "Action": "ssm:GetParameter",
                "Resource": "arn:aws:ssm:*:*:parameter/agent-orchestrator/*",
            },
            {
                "Sid": "RunLogBucketAccess",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            },
            {
                "Sid": "RunLogBucketList",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
            {
                "Sid": "DescribeOwnTags",
                "Effect": "Allow",
                "Action": "ec2:DescribeTags",
                "Resource": "*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=EC2_ROLE_NAME,
        PolicyName="agent-orchestrator-ec2-policy",
        PolicyDocument=json.dumps(inline_policy),
    )

    try:
        iam.create_instance_profile(InstanceProfileName=EC2_PROFILE_NAME)
        iam.add_role_to_instance_profile(
            InstanceProfileName=EC2_PROFILE_NAME, RoleName=EC2_ROLE_NAME
        )
        print(f"  Instance profile created: {EC2_PROFILE_NAME}")
        time.sleep(20)  # profile propagation before RunInstances references it
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"  Instance profile already exists: {EC2_PROFILE_NAME}")

    return EC2_PROFILE_NAME


def scope_self_stop_permission(iam, instance_id: str, region: str, account_id: str) -> None:
    """Grants the EC2 role StopInstances only on its own instance, once that
    instance exists -- narrower than a blanket Resource: '*' would allow."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "StopOnlySelf",
                "Effect": "Allow",
                "Action": "ec2:StopInstances",
                "Resource": f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
            }
        ],
    }
    iam.put_role_policy(
        RoleName=EC2_ROLE_NAME,
        PolicyName="agent-orchestrator-ec2-self-stop-policy",
        PolicyDocument=json.dumps(policy),
    )
    print(f"  Scoped self-stop permission to instance: {instance_id}")


def ensure_security_group(ec2, vpc_id: str) -> str:
    resp = ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [SG_NAME]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )
    if resp["SecurityGroups"]:
        sg_id = resp["SecurityGroups"][0]["GroupId"]
        print(f"  Security group already exists: {sg_id}")
        return sg_id

    resp = ec2.create_security_group(
        GroupName=SG_NAME,
        Description="agent-orchestrator: no inbound, SSM-managed only",
        VpcId=vpc_id,
    )
    sg_id = resp["GroupId"]
    print(f"  Security group created: {sg_id} (no inbound rules)")
    return sg_id


def default_vpc_id(ec2) -> str:
    resp = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not resp["Vpcs"]:
        print(
            "ERROR: no default VPC found in this region. Create a VPC or "
            "set one up manually, then adapt this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    return resp["Vpcs"][0]["VpcId"]


def bootstrap_user_data(bucket_name: str) -> str:
    # EC2 user-data (cloud-init's scripts-user module) runs ONCE PER
    # INSTANCE LIFETIME, never again on a later stop/start -- confirmed live
    # ("config-scripts-user already ran (freq=once-per-instance)" in
    # /var/log/cloud-init.log on a second start). So this first-boot-only
    # script must not contain the actual fetch-and-run logic; it installs a
    # systemd oneshot unit that runs on every future boot instead, since
    # systemd's own boot sequence isn't subject to cloud-init's semaphore.
    #
    # No `set -e` anywhere in the wrapper: a failing run.sh must never
    # prevent the trailing `shutdown -h now` from firing, or the on-demand
    # cost model breaks (the instance would run indefinitely).
    return f"""#!/bin/bash
SETUP_LOG=/var/log/agent-orchestrator-setup.log
echo "=== first-boot setup starting $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$SETUP_LOG"

# Package repo metadata isn't always ready the instant user-data starts on
# a fresh instance; refresh explicitly and retry installs rather than
# silently no-op'ing (discovered live: identical commands worked run
# manually minutes after boot, but failed silently as part of user-data).
for attempt in 1 2 3; do
    dnf makecache >> "$SETUP_LOG" 2>&1 && break
    echo "dnf makecache attempt $attempt failed, retrying..." >> "$SETUP_LOG"
    sleep 10
done

install_with_retry() {{
    local pkgs="$*"
    for attempt in 1 2 3; do
        if dnf install -y $pkgs >> "$SETUP_LOG" 2>&1; then
            return 0
        fi
        echo "dnf install ($pkgs) attempt $attempt failed, retrying..." >> "$SETUP_LOG"
        sleep 10
    done
    echo "ERROR: dnf install ($pkgs) failed after 3 attempts." >> "$SETUP_LOG"
    return 1
}}

install_with_retry git python3-pip

# PHP 8.1 (matches composer.json's ^8.1 requirement). Note: AL2023's repos
# have no pdo_sqlite package for ANY PHP version (verified live -- checked
# 8.1 through 8.5) and PECL compilation of pdo_sqlite fails against 8.1's
# Zend API (pulls an incompatible legacy source). Test isolation therefore
# uses a local MariaDB instance with its own database instead of SQLite --
# see Architecture AD-2 (amended) for the isolation mechanism this drives.
install_with_retry php8.1 php8.1-cli php8.1-common php8.1-pdo php8.1-mbstring \\
    php8.1-xml php8.1-mysqlnd php8.1-bcmath php8.1-zip
install_with_retry mariadb105-server

# Node/npm: several Blade views use @vite() -- without a built manifest,
# every such view throws ViteManifestNotFoundException and every test that
# renders one fails regardless of the actual code under test (discovered
# live: 8 of 25 baseline tests failed this way before this fix).
install_with_retry nodejs npm
systemctl enable --now mariadb >> "$SETUP_LOG" 2>&1

# MariaDB's root user defaults to unix_socket auth, which only works when
# connected as the OS root user over the local socket -- Laravel's PDO
# connection goes over TCP (127.0.0.1), which that plugin rejects
# regardless of password (discovered live: "Access denied for user
# 'root'@'localhost'" despite a correct empty password). A dedicated user
# with mysql_native_password sidesteps this rather than fighting root's
# auth plugin. Not a secret worth protecting -- this only ever holds
# throwaway test data on localhost, never reachable from outside the
# instance.
mysql -uroot -e "
CREATE DATABASE IF NOT EXISTS agent_orchestrator_test;
CREATE USER IF NOT EXISTS 'agent_orchestrator'@'127.0.0.1' IDENTIFIED BY 'agent_test_db_pw';
CREATE USER IF NOT EXISTS 'agent_orchestrator'@'localhost' IDENTIFIED BY 'agent_test_db_pw';
GRANT ALL PRIVILEGES ON agent_orchestrator_test.* TO 'agent_orchestrator'@'127.0.0.1';
GRANT ALL PRIVILEGES ON agent_orchestrator_test.* TO 'agent_orchestrator'@'localhost';
FLUSH PRIVILEGES;
" >> "$SETUP_LOG" 2>&1
export HOME=/root  # composer's installer requires HOME; unset by default in this user-data context
curl -sS https://getcomposer.org/installer 2>>"$SETUP_LOG" | php -- --install-dir=/usr/local/bin --filename=composer >> "$SETUP_LOG" 2>&1

echo "=== first-boot setup finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$SETUP_LOG"
echo "verify: php=$(command -v php || echo MISSING) composer=$(command -v composer || echo MISSING)" >> "$SETUP_LOG"

mkdir -p /opt/agent-orchestrator

cat > /opt/agent-orchestrator/fetch_and_run.sh << 'WRAPPER_EOF'
#!/bin/bash
if aws s3 cp s3://{bucket_name}/bootstrap/run.sh /tmp/run.sh 2>/tmp/fetch.log; then
    chmod +x /tmp/run.sh
    /tmp/run.sh || echo "run.sh exited non-zero: $?" >> /var/log/agent-orchestrator-boot.log
else
    echo "No bootstrap/run.sh in {bucket_name} yet -- nothing to run." >> /var/log/agent-orchestrator-boot.log
    cat /tmp/fetch.log >> /var/log/agent-orchestrator-boot.log
fi
shutdown -h now
WRAPPER_EOF
chmod +x /opt/agent-orchestrator/fetch_and_run.sh

cat > /etc/systemd/system/agent-orchestrator-boot.service << 'UNIT_EOF'
[Unit]
Description=agent-orchestrator: fetch and run bootstrap/run.sh every boot
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=HOME=/root
ExecStart=/opt/agent-orchestrator/fetch_and_run.sh
StandardOutput=append:/var/log/agent-orchestrator-boot.log
StandardError=append:/var/log/agent-orchestrator-boot.log

[Install]
WantedBy=multi-user.target
UNIT_EOF

systemctl daemon-reload
systemctl enable agent-orchestrator-boot.service
systemctl start agent-orchestrator-boot.service
"""


def ensure_ec2_instance(ec2, ssm, profile_name: str, sg_id: str, bucket_name: str) -> str:
    try:
        existing_id = ssm.get_parameter(Name=EC2_INSTANCE_ID_PARAM)["Parameter"]["Value"]
        state = ec2.describe_instances(InstanceIds=[existing_id])
        reservations = state.get("Reservations") or []
        if reservations and reservations[0].get("Instances"):
            found = reservations[0]["Instances"][0]["State"]["Name"]
            if found != "terminated":
                print(f"  EC2 instance already exists: {existing_id} ({found})")
                return existing_id
    except (ClientError, ssm.exceptions.ParameterNotFound):
        pass

    ami_id = ssm.get_parameter(Name=AL2023_AMI_PARAM)["Parameter"]["Value"]

    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t3.micro",
        MinCount=1,
        MaxCount=1,
        IamInstanceProfile={"Name": profile_name},
        SecurityGroupIds=[sg_id],
        UserData=bootstrap_user_data(bucket_name),
        InstanceInitiatedShutdownBehavior="stop",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "agent-orchestrator"}],
            }
        ],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"  EC2 instance launched: {instance_id} (will self-stop within ~1 min)")

    ssm.put_parameter(
        Name=EC2_INSTANCE_ID_PARAM,
        Value=instance_id,
        Type="String",
        Overwrite=True,
    )
    return instance_id


def ensure_lambda_role(iam, instance_id: str, region: str, account_id: str) -> str:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        resp = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )
        role_arn = resp["Role"]["Arn"]
        print(f"  IAM role created: {LAMBDA_ROLE_NAME}")
        newly_created = True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        role_arn = iam.get_role(RoleName=LAMBDA_ROLE_NAME)["Role"]["Arn"]
        print(f"  IAM role already exists: {LAMBDA_ROLE_NAME}")
        newly_created = False

    iam.attach_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadSecrets",
                "Effect": "Allow",
                "Action": "ssm:GetParameter",
                "Resource": "arn:aws:ssm:*:*:parameter/agent-orchestrator/*",
            },
            {
                "Sid": "DescribeAnyInstance",
                "Effect": "Allow",
                "Action": "ec2:DescribeInstances",
                "Resource": "*",
            },
            {
                "Sid": "ManageOnlyTheOrchestratorInstance",
                "Effect": "Allow",
                "Action": ["ec2:StartInstances", "ec2:CreateTags"],
                "Resource": f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyName="agent-orchestrator-lambda-policy",
        PolicyDocument=json.dumps(inline_policy),
    )

    if newly_created:
        time.sleep(8)  # role propagation before first CreateFunction call
    return role_arn


def build_deployment_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(HANDLER_PATH, arcname="handler.py")
    return buf.getvalue()


def ensure_lambda_function(lambda_client, role_arn: str) -> str:
    zip_bytes = build_deployment_zip()
    try:
        lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        lambda_client.update_function_code(
            FunctionName=LAMBDA_FUNCTION_NAME, ZipFile=zip_bytes
        )
        print(f"  Lambda function updated: {LAMBDA_FUNCTION_NAME}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        for attempt in range(5):
            try:
                lambda_client.create_function(
                    FunctionName=LAMBDA_FUNCTION_NAME,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="handler.handler",
                    Code={"ZipFile": zip_bytes},
                    # 60s covers up to 3 sequential GitHub calls (list +
                    # 2-step label swap) at a 10s timeout each with margin.
                    Timeout=60,
                    MemorySize=128,
                )
                print(f"  Lambda function created: {LAMBDA_FUNCTION_NAME}")
                break
            except ClientError as create_exc:
                if (
                    create_exc.response["Error"]["Code"] == "InvalidParameterValueException"
                    and attempt < 4
                ):
                    time.sleep(5)  # IAM role not yet visible to Lambda
                    continue
                raise

    resp = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
    return resp["Configuration"]["FunctionArn"]


def ensure_log_retention(logs_client) -> None:
    log_group = f"/aws/lambda/{LAMBDA_FUNCTION_NAME}"
    try:
        logs_client.create_log_group(logGroupName=log_group)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
    logs_client.put_retention_policy(logGroupName=log_group, retentionInDays=14)
    print(f"  Log retention set: {log_group} (14 days)")


def ensure_eventbridge_schedule(events_client, lambda_client, function_arn: str) -> None:
    events_client.put_rule(
        Name=EVENTBRIDGE_RULE_NAME,
        ScheduleExpression="rate(5 minutes)",
        State="ENABLED",
    )
    events_client.put_targets(
        Rule=EVENTBRIDGE_RULE_NAME,
        Targets=[{"Id": "agent-orchestrator-trigger-target", "Arn": function_arn}],
    )
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNCTION_NAME,
            StatementId="AllowEventBridgeInvoke",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
    print(f"  EventBridge rule ready: {EVENTBRIDGE_RULE_NAME} (rate(5 minutes))")


def main() -> None:
    account_id = require_aws_credentials()
    session = boto3.session.Session()
    region = session.region_name
    if not region:
        print("ERROR: no default region configured. Run `aws configure`.", file=sys.stderr)
        sys.exit(1)

    iam = session.client("iam")
    ec2 = session.client("ec2")
    ssm = session.client("ssm")
    lambda_client = session.client("lambda")
    events_client = session.client("events")
    logs_client = session.client("logs")

    bucket_name = f"{account_id}-agent-orchestrator-run-logs"

    try:
        print("Provisioning EC2 IAM role + instance profile...")
        profile_name = ensure_ec2_role(iam, bucket_name)

        print("Provisioning security group...")
        vpc_id = default_vpc_id(ec2)
        sg_id = ensure_security_group(ec2, vpc_id)

        print("Provisioning EC2 orchestrator instance...")
        instance_id = ensure_ec2_instance(ec2, ssm, profile_name, sg_id, bucket_name)
        scope_self_stop_permission(iam, instance_id, region, account_id)

        print("Provisioning Lambda IAM role...")
        lambda_role_arn = ensure_lambda_role(iam, instance_id, region, account_id)

        print("Deploying trigger Lambda...")
        function_arn = ensure_lambda_function(lambda_client, lambda_role_arn)
        ensure_log_retention(logs_client)

        print("Provisioning EventBridge schedule...")
        ensure_eventbridge_schedule(events_client, lambda_client, function_arn)
    except Exception as exc:
        print(
            f"ERROR: provisioning failed partway through: {exc}\n"
            "Re-running this script after fixing the issue is safe -- "
            "every step is idempotent and picks up where it left off.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nDone.")
    print(f"  EC2 instance: {instance_id}")
    print(f"  Lambda function: {LAMBDA_FUNCTION_NAME}")
    print(f"  EventBridge rule: {EVENTBRIDGE_RULE_NAME}")


if __name__ == "__main__":
    main()
