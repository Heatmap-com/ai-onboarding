"""Kimi (Moonshot AI) LLM adapter implementing the LLMPort Protocol.

Kimi uses an OpenAI-compatible API, so this adapter uses the ``openai``
Python SDK with a custom ``base_url`` pointing to Moonshot's servers.

Default model: ``moonshot-v1-8k`` (fast, cost-effective).
Supports structured output via JSON parsing.

API endpoint: https://api.moonshot.cn/v1
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt

T = TypeVar("T", bound=BaseModel)


class KimiAdapter:
    """Kimi (Moonshot AI) LLM adapter.

    Uses the OpenAI SDK with Moonshot's base URL. Kimi's API is fully
    OpenAI-compatible — same request format, same response format,
    different endpoint.

    Args:
        api_key: Kimi API key. Falls back to ``KIMI_API_KEY`` env var.
        model: Model identifier. Default: ``moonshot-v1-8k``.
        base_url: Kimi API base URL. Default: ``https://api.moonshot.cn/v1``.
        temperature: Sampling temperature. Default: 0.3.
        max_tokens: Max completion tokens. Default: 2000.
        timeout_seconds: Request timeout. Default: 60.0.
        telemetry: Optional telemetry port for logging.
    """

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
        self._api_key = api_key or os.getenv("KIMI_API_KEY", "")
        self._model = model
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._telemetry = telemetry
        self._client: Any = None  # Lazy init

    def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI SDK client with Kimi base URL."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a completion via Kimi API.

        Uses OpenAI-compatible chat completions endpoint.

        Args:
            prompt: Standardized prompt with system/user/context.
            config: Optional override parameters.

        Returns:
            Standardized LLMResponse.

        Raises:
            LLMCallError: On API failure, timeout, or auth error.
        """
        cfg = self._merge_config(config)
        messages = self._build_messages(prompt)

        start = time.perf_counter()
        try:
            client = self._get_client()
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=cfg.get("model", self._model),
                    messages=messages,
                    temperature=cfg.get("temperature", self._temperature),
                    max_tokens=cfg.get("max_tokens", self._max_tokens),
                ),
                timeout=cfg.get("timeout_seconds", self._timeout),
            )
            latency_ms = (time.perf_counter() - start) * 1000

            choice = response.choices[0]
            result = LLMResponse(
                content=choice.message.content or "",
                model_used=response.model or self._model,
                provider="kimi",
                tokens_used=response.usage.total_tokens if response.usage else 0,
                latency_ms=latency_ms,
                finish_reason=choice.finish_reason or "",
                metadata={
                    "prompt_tokens": (response.usage.prompt_tokens if response.usage else 0),
                    "completion_tokens": (
                        response.usage.completion_tokens if response.usage else 0
                    ),
                    "base_url": self._base_url,
                },
            )
            return result

        except TimeoutError as exc:
            raise LLMCallError(
                "Kimi request timed out",
                provider="kimi",
                retryable=True,
            ) from exc
        except Exception as exc:
            error_msg = str(exc)
            retryable = "rate_limit" in error_msg.lower() or "timeout" in error_msg.lower()
            raise LLMCallError(
                f"Kimi API error: {error_msg}",
                provider="kimi",
                retryable=retryable,
            ) from exc

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute completion with structured JSON output.

        Injects JSON formatting instructions and parses response.

        Args:
            prompt: Standardized prompt.
            output_schema: Pydantic model class.
            config: Optional override parameters.

        Returns:
            Parsed instance of ``output_schema``.

        Raises:
            LLMCallError: If JSON parsing or Pydantic validation fails.
        """
        json_prompt = self._inject_json_instructions(prompt, output_schema)
        response = await self.complete(json_prompt, config)

        try:
            content = response.content.strip()
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMCallError(
                f"Failed to parse structured output from Kimi: {exc}",
                provider="kimi",
                retryable=False,
                raw_content=response.content[:500],
            ) from exc

    @property
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            The string ``"kimi"``.
        """
        return "kimi"

    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert Prompt to OpenAI-compatible message format.

        Args:
            prompt: Standardized prompt with system/user/context.

        Returns:
            List of message dicts with ``role`` and ``content`` keys.
        """
        messages: list[dict[str, str]] = []
        if prompt.system:
            messages.append({"role": "system", "content": prompt.system})
        for ctx in prompt.context:
            messages.append({"role": ctx.get("role", "user"), "content": ctx["content"]})
        messages.append({"role": "user", "content": prompt.user})
        return messages

    def _merge_config(self, override: dict[str, Any] | None) -> dict[str, Any]:
        """Merge override config with defaults.

        Args:
            override: User-provided config overrides.

        Returns:
            Merged configuration dictionary.
        """
        base = {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "timeout_seconds": self._timeout,
        }
        if override:
            base.update(override)
        return base

    def _inject_json_instructions(
        self,
        prompt: Prompt,
        schema: type[BaseModel],
    ) -> Prompt:
        """Add JSON formatting instructions to the system prompt.

        Args:
            prompt: Original standardized prompt.
            schema: Pydantic model class to generate schema description for.

        Returns:
            New Prompt with JSON instructions appended to system message.
        """
        schema_desc = self._describe_schema(schema)
        json_instruction = (
            f"\n\nYou must respond with ONLY a valid JSON object matching "
            f"this schema. No prose, no markdown, no code blocks. "
            f"The JSON fields are: {schema_desc}"
        )
        return Prompt(
            system=prompt.system + json_instruction,
            user=prompt.user,
            context=prompt.context,
        )

    @staticmethod
    def _describe_schema(schema: type[BaseModel]) -> str:
        """Generate a human-readable description of a Pydantic schema.

        Args:
            schema: Pydantic model class.

        Returns:
            Comma-separated string of field names with their types.
        """
        fields = []
        for name, info in schema.model_fields.items():
            annotation = info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append(f"{name} ({type_name})")
        return ", ".join(fields)
