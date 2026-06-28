"""OpenAI LLM adapter implementing the LLMPort Protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brief_scout.infrastructure.llm.langchain_base import LangChainBaseAdapter

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt


class OpenAIAdapter(LangChainBaseAdapter):
    """OpenAI LLM adapter.

    Uses the official ``openai`` Python SDK with async support.
    Default model: ``gpt-4o-mini``.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout_seconds: float = 60.0,
        telemetry: Any = None,
    ) -> None:
        """Initialize the OpenAI adapter."""
        import os

        super().__init__(
            provider_name="openai",
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            telemetry=telemetry,
        )

    def _create_client(self) -> Any:
        """Create the OpenAI async client."""
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return AsyncOpenAI(**kwargs)

    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert Prompt to OpenAI message format."""
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
        """Call the OpenAI chat completions endpoint."""
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
        """Build OpenAI-specific metadata."""
        usage = self._extract_usage(response)
        return {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
        }

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Classify OpenAI errors as retryable based on message content."""
        error_msg = str(exc).lower()
        return "rate_limit" in error_msg or "timeout" in error_msg
