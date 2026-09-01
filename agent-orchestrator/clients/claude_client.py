"""The single wrapper around the Anthropic SDK (Architecture AD-6). Every
Claude call in the orchestrator goes through this -- never the raw SDK
directly -- so spend logging can never be forgotten in an individual node.
"""

import logging

import anthropic

from clients._ssm import fetch_ssm_secret
from spend_ledger import DEFAULT_MODEL, SpendCapExceeded, SpendLedger

logger = logging.getLogger(__name__)

CLAUDE_API_KEY_PARAM = "/agent-orchestrator/claude-api-key"
REQUEST_TIMEOUT_SECONDS = 120.0


class ClaudeClient:
    def __init__(
        self,
        api_key: str | None = None,
        spend_ledger: SpendLedger | None = None,
        model: str = DEFAULT_MODEL,
        run_id: str | None = None,
    ):
        self._client = anthropic.Anthropic(
            api_key=api_key or fetch_ssm_secret(CLAUDE_API_KEY_PARAM),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self.ledger = spend_ledger or SpendLedger()
        self.model = model
        self.run_id = run_id

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        node: str | None = None,
    ) -> str:
        """Sends one message-completion call and logs its real cost to the
        SpendLedger before returning, per AD-6. Refuses to call the API at
        all if the ledger already shows spend at or above the cap -- a
        defense-in-depth check; the authoritative per-Run gate lives in the
        orchestrator's node-boundary loop (AD-8), not here."""
        if not self.ledger.can_start_new_run():
            raise SpendCapExceeded(
                f"Refusing Claude API call: cumulative spend is already at "
                f"or above the RM{self.ledger.total_spend_myr():.2f} cap."
            )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

        self.ledger.record_call(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.model,
            run_id=self.run_id,
            node=node,
        )

        if response.stop_reason == "max_tokens":
            logger.warning(
                "Claude response truncated at max_tokens=%s (node=%s)",
                max_tokens,
                node,
            )

        text_blocks = [b.text for b in response.content if b.type == "text"]
        if not text_blocks:
            raise RuntimeError(
                f"Claude response contained no text content (node={node}); "
                f"stop_reason={response.stop_reason}"
            )
        return "".join(text_blocks)
