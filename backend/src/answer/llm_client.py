"""Thin wrapper around the Anthropic Messages API for answer generation (T020)."""

from functools import lru_cache
from typing import Protocol

import anthropic

from src.config import get_settings

# Chat answers are short; this caps a runaway reply without truncating real ones.
MAX_TOKENS = 4096
# Per-attempt limit. One retry keeps a slow turn bounded (~2 attempts) while the
# p95 target (8 s per turn) is met by normal requests at low effort.
REQUEST_TIMEOUT = anthropic.Timeout(15.0, connect=3.0)
MAX_RETRIES = 1


class LLMRefusalError(RuntimeError):
    """The model (and its fallback) declined to answer; callers should escalate (FR-008)."""


class LLMClientProtocol(Protocol):
    def generate(self, system: str, messages: list[dict]) -> str: ...


class LLMClient:
    def __init__(self, api_key: str, model: str, effort: str) -> None:
        self.model = model
        self.effort = effort
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES
        )

    def generate(self, system: str, messages: list[dict]) -> str:
        """Return the model's text reply.

        Raises LLMRefusalError on a refusal, and lets anthropic.APIError subclasses
        propagate so callers can tell retryable failures from bad requests.
        """
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": self.effort},
            # On a safety decline, re-run server-side on Anthropic's recommended fallback.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LLMRefusalError(f"model declined to answer (category: {category})")
        return "".join(block.text for block in response.content if block.type == "text")


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    return LLMClient(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.llm_model,
        effort=settings.llm_effort,
    )
