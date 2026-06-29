"""Shared base for real LLM adapters.

Centralizes provider-agnostic concerns:
  - config merging
  - native structured outputs with Pydantic schemas
  - retry/back-off and circuit breaker protection
  - standardized metadata shaping
  - error classification

Concrete adapters only provide:
  - client creation
  - provider-specific message formatting
  - provider-specific response parsing
  - native structured-output support when available
"""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.domain.ports.telemetry_port import LogLevel
from brief_scout.infrastructure.llm.circuit_breaker import CircuitBreaker
from brief_scout.infrastructure.llm.json_instruction_injector import (
    JsonInstructionInjector,
)
from brief_scout.infrastructure.llm.response_parser import ResponseParser
from brief_scout.infrastructure.llm.schema_describer import SchemaDescriber

if TYPE_CHECKING:
    from brief_scout.domain.ports.logger_port import LoggerPort

T = TypeVar("T", bound=BaseModel)


class LangChainBaseAdapter(ABC):
    """Abstract base for real LLM adapters.

    Provides shared concrete behavior for config merging, JSON instruction
    injection, schema description, structured parsing, retries, circuit
    breaker, and usage metadata. Subclasses implement only provider-specific
    client creation, message formatting, response parsing, retryable-error
    classification, and optional native structured-output support.
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
        max_retries: int = 3,
        telemetry: Any = None,
        json_injector: JsonInstructionInjector | None = None,
        response_parser: ResponseParser | None = None,
        circuit_breaker: CircuitBreaker | None = None,
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
            max_retries: Max retry attempts for transient failures.
            telemetry: Optional telemetry/logger port.
            json_injector: Optional JSON instruction injector.
            response_parser: Optional structured response parser.
            circuit_breaker: Optional circuit breaker instance.
        """
        self._provider_name = provider_name
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._telemetry: LoggerPort | None = telemetry
        self._client: Any | None = None
        self._json_injector = json_injector or JsonInstructionInjector()
        self._response_parser = response_parser or ResponseParser()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._last_usage: dict[str, int] | None = None
        self._last_model: str | None = None

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return self._provider_name

    @property
    def last_usage(self) -> dict[str, int] | None:
        """Return token usage from the most recent successful call."""
        return self._last_usage

    @property
    def last_model(self) -> str | None:
        """Return the model used in the most recent successful call."""
        return self._last_model

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
        """Extract the model identifier from the response."""
        ...

    @abstractmethod
    def _extract_usage(self, response: Any) -> dict[str, int]:
        """Extract token usage from the raw response.

        Returns:
            Dict with at least ``prompt_tokens`` and ``completion_tokens``.
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

    async def _call_with_retry(
        self,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        timeout: float | None = None,
    ) -> Any:
        """Execute ``fn(*args)`` with retries, circuit breaker, and timeout handling.

        ``fn`` must be a callable that returns a fresh awaitable on each call so
        that retries receive a new coroutine object.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._circuit_breaker.raise_if_open()
            try:
                coro = fn(*args)
                if timeout is not None:
                    coro = asyncio.wait_for(coro, timeout=timeout)
                result = await coro
                self._circuit_breaker.record_success()
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._circuit_breaker.record_failure()
                retryable = (
                    isinstance(exc, LLMCallError) and exc.retryable
                ) or self._is_retryable_error(exc)
                if not retryable or attempt == self._max_retries:
                    break
                delay = min(2**attempt, 10.0) + random.random()
                await asyncio.sleep(delay)

        if isinstance(last_error, LLMCallError):
            raise last_error

        if isinstance(last_error, TimeoutError):
            raise LLMCallError(
                f"{self._provider_name} request timed out",
                provider=self._provider_name,
                retryable=True,
            ) from last_error

        retryable = self._is_retryable_error(last_error) if last_error else False
        raise LLMCallError(
            f"{self._provider_name} API error: {last_error}",
            provider=self._provider_name,
            retryable=retryable,
        ) from last_error

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a single completion via the provider API."""
        cfg = self._merge_config(config)
        messages = self._build_messages(prompt)
        timeout = cfg.get("timeout_seconds", self._timeout)

        start = time.perf_counter()
        try:
            client = self._get_client()
            response = await self._call_with_retry(
                self._call_client,
                client,
                messages,
                cfg,
                timeout=timeout,
            )
            latency_ms = (time.perf_counter() - start) * 1000

            usage = self._extract_usage(response)
            model_used = self._extract_model(response)
            self._last_usage = usage
            self._last_model = model_used
            result = LLMResponse(
                content=self._extract_content(response),
                model_used=model_used,
                provider=self._provider_name,
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                finish_reason=self._extract_finish_reason(response),
                metadata={
                    "provider": self._provider_name,
                    "model": model_used,
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
        except LLMCallError:
            raise
        except Exception as exc:
            retryable = self._is_retryable_error(exc)
            raise LLMCallError(
                f"{self._provider_name} API error: {exc}",
                provider=self._provider_name,
                retryable=retryable,
            ) from exc

    async def _complete_structured_native(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Native structured output implementation; override when supported.

        Raises:
            NotImplementedError: When the provider does not support native
                structured outputs. The caller falls back to prompt-based JSON.
        """
        raise NotImplementedError(
            f"{self._provider_name} does not support native structured outputs"
        )

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute completion with structured JSON output.

        Uses native structured output when the provider supports it; otherwise
        falls back to prompt injection and JSON parsing.
        """
        try:
            return await self._complete_structured_native(prompt, output_schema, config)
        except NotImplementedError:
            pass

        json_prompt = self._json_injector.inject(prompt, output_schema)
        response = await self.complete(json_prompt, config)
        return self._response_parser.parse(
            response.content,
            output_schema,
            provider=self._provider_name,
        )

    def _inject_json_instructions(
        self,
        prompt: Prompt,
        schema: type[BaseModel],
    ) -> Prompt:
        """Add JSON formatting instructions to the system prompt.

        Deprecated: prefer ``JsonInstructionInjector.inject`` directly.
        """
        return self._json_injector.inject(prompt, schema)

    @staticmethod
    def _describe_schema(schema: type[BaseModel]) -> str:
        """Generate a human-readable description of a Pydantic schema.

        Deprecated: prefer ``SchemaDescriber.describe`` directly.
        """
        return SchemaDescriber().describe(schema)

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
