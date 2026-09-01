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

    local instance_id issue_number
    instance_id=$(get_instance_id)
    issue_number=$(get_current_issue "$instance_id")
    if [ -z "$issue_number" ] || [ "$issue_number" = "None" ]; then
        log "No CurrentIssueNumber tag found on this instance."
        issue_number=""
    else
        log "Processing issue #$issue_number."
    fi

    if reset_working_copy "$pat"; then
        if [ -n "$issue_number" ]; then
            log "Node graph not yet implemented (Stories 1.4-1.7 pending). Working copy is clean and ready at $REPO_DIR."
            # PLACEHOLDER: once Stories 1.4-1.7 exist, invoke the Python
            # orchestrator here, e.g.:
            #   python3 /opt/agent-orchestrator/orchestrator.py --issue "$issue_number"
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
