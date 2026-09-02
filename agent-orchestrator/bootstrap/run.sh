#!/bin/bash
# Fetched from s3://{bucket}/bootstrap/run.sh and executed on every boot by
# the EC2 orchestrator instance (see provision_trigger_infra.py's outer
# bootstrap stub, which self-stops the instance regardless of this script's
# exit code -- do not rely on that from in here). No `set -e`: every step
# below is handled explicitly so the final reset/cleanup always runs.

REPO_DIR=/opt/agent-orchestrator/repo
REPO_HOST_PATH="github.com/JosephSern99/Self-Management-App.git"
CLEAN_REMOTE_URL="https://${REPO_HOST_PATH}"
LOG=/var/log/agent-orchestrator-run.log
NET_TIMEOUT=60
# Generous enough for all six nodes including a full `php artisan test` run
# (which alone is capped at 300s) plus Claude API latency, but bounded --
# a hung node/API call must never leave the on-demand instance running
# indefinitely, or it breaks the $0 AWS-cost invariant (AD-4).
RUN_TIMEOUT=1800

log() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG"
}

# Strips the PAT out of anything piped through it before it reaches the log,
# so a git auth-failure message that echoes the remote URL (which git does)
# never persists the token in plaintext on disk.
redact_and_log() {
    local pat="$1"
    if [ -n "$pat" ]; then
        sed "s/${pat//\//\\/}/REDACTED/g" | tee -a "$LOG" >/dev/null
    else
        tee -a "$LOG" >/dev/null
    fi
}

get_github_pat() {
    timeout "$NET_TIMEOUT" aws ssm get-parameter \
        --name /agent-orchestrator/github-pat \
        --with-decryption \
        --query Parameter.Value \
        --output text 2>>"$LOG"
}

get_instance_id() {
    local token id
    token=$(timeout 10 curl -s -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    if [ -z "$token" ]; then
        log "ERROR: could not obtain IMDSv2 token."
        return 1
    fi
    id=$(timeout 10 curl -s -H "X-aws-ec2-metadata-token: $token" \
        http://169.254.169.254/latest/meta-data/instance-id)
    if [ -z "$id" ]; then
        log "ERROR: could not resolve instance id from IMDS."
        return 1
    fi
    echo "$id"
}

# boto3 (unlike the AWS CLI, which auto-detects region from IMDS) requires
# an explicit region -- discovered live: orchestrator.py failed every AWS
# call with botocore.exceptions.NoRegionError despite the AWS CLI calls
# elsewhere in this same script working fine. Same IMDSv2 pattern as
# get_instance_id().
get_region() {
    local token region
    token=$(timeout 10 curl -s -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    if [ -z "$token" ]; then
        log "ERROR: could not obtain IMDSv2 token for region lookup."
        return 1
    fi
    region=$(timeout 10 curl -s -H "X-aws-ec2-metadata-token: $token" \
        http://169.254.169.254/latest/meta-data/placement/region)
    if [ -z "$region" ]; then
        log "ERROR: could not resolve region from IMDS."
        return 1
    fi
    echo "$region"
}

get_current_issue() {
    local instance_id="$1"
    local out
    out=$(timeout "$NET_TIMEOUT" aws ec2 describe-tags \
        --filters "Name=resource-id,Values=$instance_id" "Name=key,Values=CurrentIssueNumber" \
        --query "Tags[0].Value" --output text 2>>"$LOG")
    if [ $? -ne 0 ]; then
        log "ERROR: describe-tags call failed; treating as no issue."
        return 1
    fi
    echo "$out"
}

# Removes a working copy that isn't a valid git repo (e.g. left behind by an
# instance killed mid-clone), so it doesn't get mistaken for "existing" on
# every subsequent boot forever.
discard_if_corrupt() {
    if [ -d "$REPO_DIR" ] && ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log "Existing directory is not a valid git repo -- discarding."
        rm -rf "$REPO_DIR"
    fi
}

# Brings the working copy to a clean origin/main: clone on first boot,
# fetch+hard-reset+clean thereafter. `reset --hard` alone leaves untracked
# files behind, so `git clean -fd` runs too -- required by AD-5's "never
# left dirty" invariant, not optional cleanup. The PAT is only ever placed
# in a remote URL for the single command that needs it, and the remote is
# immediately reset to a credential-less URL afterward so nothing persists
# in .git/config at rest.
reset_working_copy() {
    local pat="$1"

    discard_if_corrupt

    if [ ! -d "$REPO_DIR/.git" ]; then
        log "No existing working copy -- cloning fresh."
        mkdir -p "$(dirname "$REPO_DIR")" || {
            log "ERROR: could not create $(dirname "$REPO_DIR")."
            return 1
        }
        timeout "$NET_TIMEOUT" git clone \
            "https://x-access-token:${pat}@${REPO_HOST_PATH}" "$REPO_DIR" \
            2>&1 | redact_and_log "$pat"
        if [ ! -d "$REPO_DIR/.git" ]; then
            log "ERROR: clone failed."
            return 1
        fi
        git -C "$REPO_DIR" remote set-url origin "$CLEAN_REMOTE_URL"
        log "Clone succeeded."
        return 0
    fi

    log "Existing working copy found -- resetting to origin/main."
    git -C "$REPO_DIR" remote set-url origin "https://x-access-token:${pat}@${REPO_HOST_PATH}"
    (
        timeout "$NET_TIMEOUT" git -C "$REPO_DIR" fetch origin main \
            && git -C "$REPO_DIR" reset --hard origin/main \
            && git -C "$REPO_DIR" clean -fd
    ) 2>&1 | redact_and_log "$pat"
    local result=${PIPESTATUS[0]}
    git -C "$REPO_DIR" remote set-url origin "$CLEAN_REMOTE_URL"

    if [ "$result" -ne 0 ]; then
        log "ERROR: fetch/reset/clean failed; working copy left in its prior state."
        return 1
    fi
    log "Reset complete."
    return 0
}

# vendor/ and node_modules/ are both gitignored, so they survive
# `git clean -fd` (not `-fdx`) across resets -- these only need to run once
# per instance lifetime, or again if the lockfiles changed since the last
# successful install.
ensure_composer_dependencies() {
    if [ -f "$REPO_DIR/vendor/autoload.php" ]; then
        log "Composer dependencies already installed."
        return 0
    fi
    log "Installing Composer dependencies..."
    # HOME isn't set by default under systemd's execution context (this
    # script runs via the agent-orchestrator-boot.service unit) and
    # Composer requires it -- discovered live via the same failure in the
    # first-boot user-data context.
    if (export HOME=/root; cd "$REPO_DIR" && composer install --no-interaction --no-progress) >>"$LOG" 2>&1; then
        log "Composer install complete."
    else
        log "ERROR: composer install failed."
    fi
}

# requirements.txt (boto3, anthropic) only needs installing once per
# instance lifetime, same idempotent-if-missing shape as
# ensure_composer_dependencies -- checks for the anthropic package's
# presence rather than re-running pip on every single boot.
#
# Uses python3.12 explicitly, never the bare `python3` this script uses
# elsewhere for its own IMDS/tag helpers -- discovered live: AL2023's
# default `python3` resolves to 3.9, but the `anthropic` SDK's 1.x releases
# require Python >=3.10, so a plain `python3 -m pip install` only ever finds
# pre-1.0 anthropic versions on PyPI and fails outright. python3.12 (with
# its own bundled modern pip) is present on this AMI already and installs
# both dependencies cleanly with no further pip-upgrade workaround needed.
#
# Self-heals rather than relying solely on provision_trigger_infra.py's
# first-boot user-data (which never reruns on an already-provisioned
# instance, per cloud-init's once-per-instance semaphore -- see
# bootstrap_user_data()'s own comment) -- discovered live: an instance
# provisioned before python3.12/pip were confirmed present in that
# user-data would otherwise never recover without a manual
# terminate/recreate. Same self-healing precedent as this file's existing
# git-availability handling.
ensure_python_dependencies() {
    if python3.12 -c "import boto3, anthropic" >/dev/null 2>&1; then
        log "Python dependencies already installed."
        return 0
    fi
    if ! command -v python3.12 >/dev/null 2>&1 || ! python3.12 -m pip --version >/dev/null 2>&1; then
        log "python3.12/pip missing -- installing python3.12 python3.12-pip..."
        if ! timeout "$NET_TIMEOUT" sudo dnf install -y python3.12 python3.12-pip >>"$LOG" 2>&1; then
            log "ERROR: dnf install python3.12 python3.12-pip failed."
            return 1
        fi
    fi
    log "Installing Python dependencies..."
    if python3.12 -m pip install --quiet -r "$REPO_DIR/agent-orchestrator/requirements.txt" >>"$LOG" 2>&1; then
        log "Python dependencies installed."
        return 0
    else
        log "ERROR: pip install -r requirements.txt failed."
        return 1
    fi
}

# Blade views using @vite() throw ViteManifestNotFoundException without a
# built manifest -- discovered live: every such test failed regardless of
# the actual code under test until this was added.
ensure_frontend_assets() {
    if [ -f "$REPO_DIR/public/build/manifest.json" ]; then
        log "Frontend assets already built."
        return 0
    fi
    log "Installing npm dependencies and building frontend assets..."
    if (cd "$REPO_DIR" && npm install --no-audit --no-fund && npm run build) >>"$LOG" 2>&1; then
        log "Frontend build complete."
    else
        log "ERROR: npm install/build failed."
    fi
}

main() {
    log "=== agent-orchestrator run.sh starting ==="
    local exit_code=0

    local pat
    pat=$(get_github_pat)
    if [ -z "$pat" ]; then
        log "ERROR: could not read GitHub PAT from SSM. Attempting local-only cleanup, then aborting."
        discard_if_corrupt
        [ -d "$REPO_DIR/.git" ] && git -C "$REPO_DIR" clean -fd >>"$LOG" 2>&1
        exit 1
    fi

    local instance_id issue_number region
    instance_id=$(get_instance_id)
    issue_number=$(get_current_issue "$instance_id")
    if [ -z "$issue_number" ] || [ "$issue_number" = "None" ]; then
        log "No CurrentIssueNumber tag found on this instance."
        issue_number=""
    else
        log "Processing issue #$issue_number."
    fi

    if reset_working_copy "$pat"; then
        ensure_composer_dependencies
        ensure_frontend_assets

        if ! ensure_python_dependencies; then
            log "ERROR: Python dependencies unavailable -- skipping orchestrator invocation."
            exit_code=1
        elif [ -n "$issue_number" ]; then
            log "Running orchestrator for issue #$issue_number."
            region=$(get_region)
            if [ -z "$region" ]; then
                log "ERROR: could not resolve AWS region -- boto3 requires one explicitly (unlike the AWS CLI's IMDS auto-detection). Skipping orchestrator invocation."
                exit_code=1
            else
                AWS_DEFAULT_REGION="$region" timeout "$RUN_TIMEOUT" python3.12 "$REPO_DIR/agent-orchestrator/orchestrator.py" --issue "$issue_number" >>"$LOG" 2>&1
                exit_code=$?
                log "Orchestrator finished for issue #$issue_number (exit $exit_code)."
            fi
        else
            log "No issue to process this boot; lifecycle scaffold verified only."
        fi
    else
        log "Initial reset failed -- skipping run body, still cleaning up."
        exit_code=1
    fi

    log "Final reset before shutdown."
    if ! reset_working_copy "$pat"; then
        log "WARNING: final reset failed; instance will still stop."
        exit_code=1
    fi

    unset pat
    log "=== agent-orchestrator run.sh finished (exit $exit_code) ==="
    exit $exit_code
}

main
