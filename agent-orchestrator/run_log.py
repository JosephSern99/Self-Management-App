"""Durable per-Run trace, written once to S3 so a Run's plan, diffs, test
output, and outcome survive after the on-demand EC2 instance that produced
them stops. `RunLog` accumulates a snapshot of `RunState` after each node
via `record_node()`, then `finalize()` records the Run's outcome; the
orchestrator (not built here -- deferred from Story 1.7) is expected to
call both at each node boundary and once at the end, then call
`persist_run_log()`. Standalone and independently testable -- this module
does not wire the six nodes together.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import boto3

from state import RunState

logger = logging.getLogger(__name__)


class RunLogPersistError(RuntimeError):
    pass


@dataclass
class RunLog:
    run_id: str
    issue_number: int | None
    node_trace: list = field(default_factory=list)
    outcome: str = ""
    outcome_reason: str = ""

    def record_node(self, node_name: str, state: RunState) -> None:
        # Shallow snapshot of the fields relevant at this point in the
        # pipeline -- not dataclasses.asdict(state), since state.ticket may
        # carry a large GitHub issue body we don't want repeated once per
        # node in the trace.
        self.node_trace.append(
            {
                "node": node_name,
                "plan": state.plan,
                "file_targets": list(state.file_targets),
                "diff": state.diff,
                "test_result": dict(state.test_result),
                "review_verdict": state.review_verdict,
                "spend_used": state.spend_used,
            }
        )

    def finalize(self, outcome: str, reason: str = "") -> None:
        self.outcome = outcome
        self.outcome_reason = reason

    def to_json(self) -> str:
        return json.dumps(
            {
                "run_id": self.run_id,
                "issue_number": self.issue_number,
                "node_trace": self.node_trace,
                "outcome": self.outcome,
                "outcome_reason": self.outcome_reason,
            },
            indent=2,
            default=str,
        )


def persist_run_log(run_log: RunLog, bucket_name: str, s3_client=None) -> str:
    if run_log.issue_number is None:
        raise ValueError("Cannot persist run log: run_log.issue_number is None")
    if not run_log.outcome:
        raise ValueError("Cannot persist run log: finalize() was not called")

    s3 = s3_client or boto3.client("s3")
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"runs/{run_log.issue_number}/{run_timestamp}/run_log.json"

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=run_log.to_json().encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as exc:
        logger.error("Failed to persist run log to s3://%s/%s: %s", bucket_name, key, exc)
        raise RunLogPersistError(f"Could not persist run log to s3://{bucket_name}/{key}: {exc}") from exc

    logger.info("Persisted run log to s3://%s/%s", bucket_name, key)
    return key
