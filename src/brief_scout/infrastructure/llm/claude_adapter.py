"""Anthropic Claude LLM adapter implementing the LLMPort Protocol.

Uses the official ``anthropic`` Python SDK with async support.
Default model: ``claude-3-haiku-20240307`` (fast, cost-effective).
Supports structured output via JSON parsing.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt

T = TypeVar("T", bound=BaseModel)


class ClaudeAdapter:
    """Anthropic Claude LLM adapter.

    Implements ``LLMPort`` using the Anthropic SDK. Claude uses a
    separate ``system`` parameter (not a message role) for system
    prompts, and returns content via ``response.content[0].text``.

    Args:
        api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
        model: Model identifier. Default: ``claude-3-haiku-20240307``.
        base_url: Optional custom base URL.
        temperature: Sampling temperature. Default: 0.3.
        max_tokens: Max completion tokens. Default: 2000.
        timeout_seconds: Request timeout. Default: 60.0.
        telemetry: Optional telemetry port for logging.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-3-haiku-20240307",
        base_url: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout_seconds: float = 60.0,
        telemetry: Any = None,
    ) -> None:
        import os

        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._telemetry = telemetry
        self._client: Any = None  # Lazy init

    def _get_client(self) -> Any:
        """Lazy-initialize the Anthropic async client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncAnthropic(**kwargs)
        return self._client

    async def complete(self, prompt: Prompt, config: dict[str, Any] | None = None) -> LLMResponse:
        """Execute a completion via Claude API.

        Claude's API uses a separate ``system`` parameter and returns
        content in ``response.content[0].text``.

        Args:
            prompt: Standardized prompt.
            config: Optional override parameters.

        Returns:
            Standardized LLMResponse.

        Raises:
            LLMCallError: On API failure, timeout, or auth error.
        """
        cfg = self._merge_config(config)
        messages = self._build_messages(prompt)
        system = prompt.system if prompt.system else None

        start = time.perf_counter()
        try:
            client = self._get_client()
            kwargs: dict[str, Any] = {
                "model": cfg.get("model", self._model),
                "messages": messages,
                "max_tokens": cfg.get("max_tokens", self._max_tokens),
                "temperature": cfg.get("temperature", self._temperature),
            }
            if system:
                kwargs["system"] = system

            response = await asyncio.wait_for(
                client.messages.create(**kwargs),
                timeout=cfg.get("timeout_seconds", self._timeout),
            )
            latency_ms = (time.perf_counter() - start) * 1000

            content = ""
            if response.content and len(response.content) > 0:
                content = response.content[0].text

            # Extract usage if available
            input_tokens = (
                getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
            )
            output_tokens = (
                getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
            )

            result = LLMResponse(
                content=content,
                model_used=response.model or self._model,
                provider="claude",
                tokens_used=input_tokens + output_tokens,
                latency_ms=latency_ms,
                finish_reason=response.stop_reason or "",
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "stop_sequence": response.stop_sequence,
                },
            )
            return result

        except TimeoutError as exc:
            raise LLMCallError(
                "Claude request timed out",
                provider="claude",
                retryable=True,
            ) from exc
        except Exception as exc:
            error_msg = str(exc)
            error_lower = error_msg.lower()
            retryable = (
                "rate_limit" in error_lower
                or "rate limit" in error_lower
                or "timeout" in error_lower
            )
            raise LLMCallError(
                f"Claude API error: {error_msg}",
                provider="claude",
                retryable=retryable,
            ) from exc

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute completion with structured JSON output.

        Injects JSON instructions into the system prompt and parses
        the response into a Pydantic model.

        Args:
            prompt: Standardized prompt.
            output_schema: Pydantic model class.
            config: Optional override parameters.

        Returns:
            Parsed instance of ``output_schema``.
        """
        json_prompt = self._inject_json_instructions(prompt, output_schema)
        response = await self.complete(json_prompt, config)

        try:
            content = response.content.strip()
            # Strip markdown code blocks if present
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
                f"Failed to parse structured output from Claude: {exc}",
                provider="claude",
                retryable=False,
                raw_content=response.content[:500],
            ) from exc

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "claude"

    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert Prompt to Claude message format.

        Claude does NOT support system role in messages -- system goes
        in a separate parameter. This method builds only user/assistant
        messages from the context, plus the final user message.
        """
        messages: list[dict[str, str]] = []
        for ctx in prompt.context:
            role = ctx.get("role", "user")
            if role != "system":  # Claude doesn't allow system in messages
                messages.append({"role": role, "content": ctx["content"]})
        messages.append({"role": "user", "content": prompt.user})
        return messages

    def _merge_config(self, override: dict[str, Any] | None) -> dict[str, Any]:
        """Merge override config with defaults."""
        base = {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "timeout_seconds": self._timeout,
        }
        if override:
            base.update(override)
        return base

    def _inject_json_instructions(self, prompt: Prompt, schema: type[BaseModel]) -> Prompt:
        """Add JSON formatting instructions to the system prompt."""
        schema_desc = self._describe_schema(schema)
        json_instruction = (
            f"\n\nYou must respond with ONLY a valid JSON object matching this schema. "
            f"No prose, no markdown, no code blocks. The JSON fields are: {schema_desc}"
        )
        return Prompt(
            system=prompt.system + json_instruction,
            user=prompt.user,
            context=prompt.context,
        )

    @staticmethod
    def _describe_schema(schema: type[BaseModel]) -> str:
        """Generate a human-readable description of a Pydantic schema."""
        fields = []
        for name, info in schema.model_fields.items():
            annotation = info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append(f"{name} ({type_name})")
        return ", ".join(fields)
