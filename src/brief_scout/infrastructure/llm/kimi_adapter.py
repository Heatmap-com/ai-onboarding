"""Kimi (Moonshot AI) LLM adapter implementing the LLMPort Protocol.

Kimi uses an OpenAI-compatible API with a custom base URL.
Default model: ``moonshot-v1-8k``.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from brief_scout.infrastructure.llm.langchain_base import LangChainBaseAdapter

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt


class KimiAdapter(LangChainBaseAdapter):
    """Kimi (Moonshot AI) LLM adapter."""

    DEFAULT_BASE_URL: str = "https://api.moonshot.cn/v1"

    def __init__(
        self,
        api_key: str = "",
        model: str = "moonshot-v1-8k",
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout_seconds: float = 60.0,
        telemetry: Any = None,
    ) -> None:
        """Initialize the Kimi adapter."""
        super().__init__(
            provider_name="kimi",
            api_key=api_key or os.getenv("KIMI_API_KEY", ""),
            model=model,
            base_url=base_url or self.DEFAULT_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            telemetry=telemetry,
        )

    def _create_client(self) -> Any:
        """Create the OpenAI SDK client with Kimi base URL."""
        from openai import AsyncOpenAI

        return AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert Prompt to OpenAI-compatible message format."""
        messages: list[dict[str, str]] = []
        if prompt.system:
            messages.append({"role": "system", "content": prompt.system})
        for ctx in prompt.context:
            messages.append({"role": ctx.get("role", "user"), "content": ctx["content"]})
        messages.append({"role": "user", "content": prompt.user})
        return messages

    async def _call_client(
        self,
        client: Any,
        messages: list[dict[str, str]],
        cfg: dict[str, Any],
    ) -> Any:
        """Call the Kimi chat completions endpoint."""
        return await client.chat.completions.create(
            model=cfg.get("model", self._model),
            messages=messages,
            temperature=cfg.get("temperature", self._temperature),
            max_tokens=cfg.get("max_tokens", self._max_tokens),
        )

    def _extract_content(self, response: Any) -> str:
        """Extract text content from the response."""
        return response.choices[0].message.content or ""

    def _extract_model(self, response: Any) -> str:
        """Extract model identifier from the response."""
        return response.model or self._model

    def _extract_usage(self, response: Any) -> dict[str, int]:
        """Extract token usage from the response."""
        if response.usage:
            return {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _extract_finish_reason(self, response: Any) -> str:
        """Extract finish reason from the response."""
        return response.choices[0].finish_reason or ""

    def _build_provider_metadata(self, response: Any) -> dict[str, Any]:
        """Build Kimi-specific metadata."""
        usage = self._extract_usage(response)
        return {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "base_url": self._base_url,
        }

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Classify Kimi errors as retryable based on message content."""
        error_msg = str(exc).lower()
        return "rate_limit" in error_msg or "timeout" in error_msg
