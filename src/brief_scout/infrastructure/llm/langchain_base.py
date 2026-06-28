"""Shared base for real LLM adapters.

Centralizes provider-agnostic concerns:
  - config merging
  - JSON instruction injection
  - schema description
  - structured-output parsing
  - standardized metadata shaping
  - error classification

Concrete adapters only provide:
  - client creation
  - provider-specific message formatting
  - provider-specific response parsing
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.domain.ports.telemetry_port import LogLevel

if TYPE_CHECKING:
    from brief_scout.domain.ports.logger_port import LoggerPort

T = TypeVar("T", bound=BaseModel)


class LangChainBaseAdapter(ABC):
    """Abstract base for real LLM adapters.

    Provides shared concrete behavior for config merging, JSON instruction
    injection, schema description, and structured parsing. Subclasses
    implement only provider-specific client creation, message formatting,
    response parsing, and retryable-error classification.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str = "",
        model: str = "",
        base_url: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout_seconds: float = 60.0,
        telemetry: Any = None,
    ) -> None:
        """Initialize the base adapter.

        Args:
            provider_name: Provider identifier string.
            api_key: API key for the provider.
            model: Model identifier.
            base_url: Optional custom base URL.
            temperature: Sampling temperature.
            max_tokens: Max completion tokens.
            timeout_seconds: Request timeout.
            telemetry: Optional telemetry/logger port.
        """
        self._provider_name = provider_name
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._telemetry: LoggerPort | None = telemetry
        self._client: Any | None = None

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return self._provider_name

    @abstractmethod
    def _create_client(self) -> Any:
        """Create and return the provider-specific async client."""
        ...

    @abstractmethod
    def _build_messages(self, prompt: Prompt) -> list[dict[str, str]]:
        """Convert a standardized Prompt into provider message format."""
        ...

    @abstractmethod
    async def _call_client(
        self,
        client: Any,
        messages: list[dict[str, str]],
        cfg: dict[str, Any],
    ) -> Any:
        """Call the provider client and return the raw response."""
        ...

    @abstractmethod
    def _extract_content(self, response: Any) -> str:
        """Extract text content from the raw response."""
        ...

    @abstractmethod
    def _extract_model(self, response: Any) -> str:
        """Extract the model identifier from the raw response."""
        ...

    @abstractmethod
    def _extract_usage(self, response: Any) -> dict[str, int]:
        """Extract token usage from the raw response.

        Returns:
            Dict with at least "prompt_tokens" and "completion_tokens".
        """
        ...

    @abstractmethod
    def _extract_finish_reason(self, response: Any) -> str:
        """Extract finish reason from the raw response."""
        ...

    @abstractmethod
    def _build_provider_metadata(self, response: Any) -> dict[str, Any]:
        """Build provider-specific metadata sub-dictionary."""
        ...

    @abstractmethod
    def _is_retryable_error(self, exc: Exception) -> bool:
        """Return True if the exception represents a transient failure."""
        ...

    def _get_client(self) -> Any:
        """Lazy-initialize the provider client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a single completion via the provider API."""
        cfg = self._merge_config(config)
        messages = self._build_messages(prompt)

        start = time.perf_counter()
        try:
            client = self._get_client()
            response = await asyncio.wait_for(
                self._call_client(client, messages, cfg),
                timeout=cfg.get("timeout_seconds", self._timeout),
            )
            latency_ms = (time.perf_counter() - start) * 1000

            usage = self._extract_usage(response)
            result = LLMResponse(
                content=self._extract_content(response),
                model_used=self._extract_model(response),
                provider=self._provider_name,
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                finish_reason=self._extract_finish_reason(response),
                metadata={
                    "provider": self._provider_name,
                    "model": self._extract_model(response),
                    "tokens_used": usage.get("total_tokens", 0),
                    "latency_ms": latency_ms,
                    "provider_metadata": self._build_provider_metadata(response),
                },
            )
            return result

        except TimeoutError as exc:
            raise LLMCallError(
                f"{self._provider_name} request timed out",
                provider=self._provider_name,
                retryable=True,
            ) from exc
        except Exception as exc:
            retryable = self._is_retryable_error(exc)
            raise LLMCallError(
                f"{self._provider_name} API error: {exc}",
                provider=self._provider_name,
                retryable=retryable,
            ) from exc

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute completion with structured JSON output."""
        json_prompt = self._inject_json_instructions(prompt, output_schema)
        response = await self.complete(json_prompt, config)

        try:
            content = self._strip_markdown_code_blocks(response.content)
            data = json.loads(content)
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMCallError(
                f"Failed to parse structured output: {exc}",
                provider=self._provider_name,
                retryable=False,
                raw_content=response.content[:500],
            ) from exc

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

    def _inject_json_instructions(
        self,
        prompt: Prompt,
        schema: type[BaseModel],
    ) -> Prompt:
        """Add JSON formatting instructions to the system prompt."""
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
        """Generate a human-readable description of a Pydantic schema."""
        fields = []
        for name, info in schema.model_fields.items():
            annotation = info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append(f"{name} ({type_name})")
        return ", ".join(fields)

    @staticmethod
    def _strip_markdown_code_blocks(content: str) -> str:
        """Remove markdown code fences from JSON content."""
        text = content.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _handle_error(
        self,
        exc: Exception,
        operation: str,
        retryable: bool = True,
    ) -> None:
        """Log an error via the telemetry/logger port if available."""
        if self._telemetry is not None:
            self._telemetry.log(
                message=f"LLM {operation} failed: {exc}",
                level=LogLevel.ERROR,
                provider=self._provider_name,
                operation=operation,
                error_type=type(exc).__name__,
                retryable=retryable,
            )
