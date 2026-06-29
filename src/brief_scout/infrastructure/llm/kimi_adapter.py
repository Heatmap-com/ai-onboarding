"""Kimi (Moonshot AI) LLM adapter implementing the LLMPort Protocol.

Kimi uses an OpenAI-compatible API with a custom base URL.
Default model: ``moonshot-v1-8k``.
"""

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.infrastructure.llm.langchain_base import LangChainBaseAdapter

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt

T = TypeVar("T", bound=BaseModel)


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
        max_retries: int = 3,
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
            max_retries=max_retries,
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
            messages.append({"role": ctx.role, "content": ctx.content})
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
        if isinstance(exc, TimeoutError):
            return True
        error_msg = str(exc).lower()
        retryable_keywords = (
            "rate_limit",
            "timeout",
            "temporarily unavailable",
            "overloaded",
            "internal_error",
            "bad gateway",
            "service unavailable",
            "connection",
        )
        return any(keyword in error_msg for keyword in retryable_keywords)

    async def _complete_structured_native(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Use Kimi's OpenAI-compatible JSON response format when supported."""
        cfg = self._merge_config(config)
        json_prompt = self._json_injector.inject(prompt, output_schema)
        messages = self._build_messages(json_prompt)
        schema = output_schema.model_json_schema()
        name = schema.get("title", output_schema.__name__)

        client = self._get_client()
        response = await self._call_with_retry(
            partial(
                client.chat.completions.create,
                model=cfg.get("model", self._model),
                messages=messages,
                temperature=cfg.get("temperature", self._temperature),
                max_tokens=cfg.get("max_tokens", self._max_tokens),
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": name,
                        "schema": schema,
                        "strict": True,
                    },
                },
            ),
            timeout=cfg.get("timeout_seconds", self._timeout),
        )

        content = self._extract_content(response)
        usage = self._extract_usage(response)
        model_used = self._extract_model(response)
        self._last_usage = usage
        self._last_model = model_used

        if not content:
            raise LLMCallError(
                "Kimi returned empty structured output",
                provider=self._provider_name,
                retryable=False,
            )

        return self._response_parser.parse(
            content,
            output_schema,
            provider=self._provider_name,
        )
