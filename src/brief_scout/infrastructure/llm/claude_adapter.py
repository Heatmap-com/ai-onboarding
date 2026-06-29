"""Anthropic Claude LLM adapter implementing the LLMPort Protocol."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from brief_scout.infrastructure.llm.langchain_base import LangChainBaseAdapter

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt


class ClaudeAdapter(LangChainBaseAdapter):
    """Anthropic Claude LLM adapter.

    Uses the official ``anthropic`` Python SDK with async support.
    Default model: ``claude-3-haiku-20240307``.

    Claude uses a separate ``system`` parameter (not a message role) and
    returns content via ``response.content[0].text``. System context items
    from ``prompt.context`` are appended to the system parameter so they are
    preserved rather than silently dropped.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-3-haiku-20240307",
        base_url: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        telemetry: Any = None,
    ) -> None:
        """Initialize the Claude adapter."""
        super().__init__(
            provider_name="claude",
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            telemetry=telemetry,
        )
        self._last_system: str | None = None

    def _create_client(self) -> Any:
        """Create the Anthropic async client."""
        from anthropic import AsyncAnthropic

        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return AsyncAnthropic(**kwargs)

    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert Prompt to Claude message format.

        Claude does not allow a system role inside messages. System prompts
        are handled separately via the ``system`` API parameter; any system
        context items are aggregated in ``_call_client``.
        """
        messages: list[dict[str, str]] = []
        for ctx in prompt.context:
            if ctx.role != "system":
                messages.append({"role": ctx.role, "content": ctx.content})
        messages.append({"role": "user", "content": prompt.user})
        return messages

    def _build_system_param(self, prompt: Prompt) -> str | None:
        """Aggregate system prompt and system-role context items."""
        system_parts: list[str] = []
        if prompt.system:
            system_parts.append(prompt.system)
        for ctx in prompt.context:
            if ctx.role == "system":
                system_parts.append(ctx.content)
        return "\n\n".join(system_parts) if system_parts else None

    async def _call_client(
        self,
        client: Any,
        messages: list[dict[str, str]],
        cfg: dict[str, Any],
    ) -> Any:
        """Call the Claude messages endpoint."""
        system = self._last_system
        kwargs: dict[str, Any] = {
            "model": cfg.get("model", self._model),
            "messages": messages,
            "max_tokens": cfg.get("max_tokens", self._max_tokens),
            "temperature": cfg.get("temperature", self._temperature),
        }
        if system:
            kwargs["system"] = system
        return await client.messages.create(**kwargs)

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a single completion via Claude API.

        Stores the system prompt so _call_client can pass it separately.
        """
        self._last_system = self._build_system_param(prompt)
        return await super().complete(prompt, config)

    def _extract_content(self, response: Any) -> str:
        """Extract text content from the Claude response."""
        if response.content and len(response.content) > 0:
            return str(response.content[0].text)
        return ""

    def _extract_model(self, response: Any) -> str:
        """Extract model identifier from the response."""
        return response.model or self._model

    def _extract_usage(self, response: Any) -> dict[str, int]:
        """Extract token usage from the response."""
        if hasattr(response, "usage") and response.usage:
            input_tokens = getattr(response.usage, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0
            return {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _extract_finish_reason(self, response: Any) -> str:
        """Extract finish reason from the response."""
        return response.stop_reason or ""

    def _build_provider_metadata(self, response: Any) -> dict[str, Any]:
        """Build Claude-specific metadata."""
        usage = self._extract_usage(response)
        return {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "stop_sequence": response.stop_sequence,
        }

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Classify Claude errors as retryable based on message content."""
        if isinstance(exc, TimeoutError):
            return True
        error_msg = str(exc).lower()
        retryable_keywords = (
            "rate_limit",
            "rate limit",
            "timeout",
            "temporarily unavailable",
            "overloaded",
            "internal_error",
            "bad gateway",
            "service unavailable",
            "connection",
        )
        return any(keyword in error_msg for keyword in retryable_keywords)
