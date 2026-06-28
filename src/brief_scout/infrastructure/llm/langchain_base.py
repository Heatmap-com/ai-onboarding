"""LangChain base adapter — minimal base class for future real LLM adapters.

This module provides the foundation for integrating with real LLM providers
(OpenAI, Anthropic, etc.) through LangChain. The FakeLLMAdapter is the
primary adapter for the MVP, but this base class ensures the architecture
can accommodate real providers without structural changes.

When implementing a real adapter:
1. Inherit from LangChainBaseAdapter
2. Override _create_client() to return a LangChain chat model
3. Override provider_name to return the provider identifier
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import LLMResponse, Prompt

T = TypeVar("T", bound=BaseModel)


class LangChainBaseAdapter(ABC):
    """Abstract base for LangChain-based LLM adapters.

    Provides common infrastructure for real LLM adapters: prompt formatting,
    response parsing, and error handling. Concrete subclasses implement
    the provider-specific client creation.

    Attributes:
        provider_config: Dictionary of provider-specific settings.
        telemetry: Optional telemetry port for logging.
    """

    def __init__(
        self,
        provider_config: dict[str, Any] | None = None,
        telemetry: Any | None = None,
    ) -> None:
        """Initialize the base adapter.

        Args:
            provider_config: Provider-specific configuration (model name,
                temperature, API key, base URL, etc.).
            telemetry: Optional telemetry port for observability.
        """
        self._provider_config = provider_config or {}
        self._telemetry = telemetry
        self._client: Any | None = None

    @abstractmethod
    def _create_client(self) -> Any:
        """Create and return a LangChain chat model client.

        Subclasses must implement this to return their specific
        LangChain chat model instance (e.g., ChatOpenAI, ChatAnthropic).

        Returns:
            A LangChain BaseChatModel subclass instance.
        """
        ...

    @abstractmethod
    def _format_messages(self, prompt: Prompt) -> list[Any]:
        """Convert a standardized Prompt into LangChain message format.

        Subclasses may override to support provider-specific message formats.

        Args:
            prompt: The standardized prompt.

        Returns:
            A list of LangChain message objects.
        """
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a single LLM completion.

        Subclasses must implement the actual LLM call logic.

        Args:
            prompt: The standardized prompt.
            config: Optional provider-specific overrides.

        Returns:
            An LLMResponse with the generated content.
        """
        ...

    @abstractmethod
    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute LLM completion with structured output.

        Subclasses should use provider-specific structured output
        capabilities (e.g., function calling, JSON mode).

        Args:
            prompt: The standardized prompt.
            output_schema: Pydantic model class to parse into.
            config: Optional provider-specific overrides.

        Returns:
            An instance of output_schema.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            Provider identifier string (e.g., 'openai', 'anthropic', 'kimi').
        """
        ...

    def _handle_error(
        self,
        exc: Exception,
        operation: str,
        retryable: bool = True,
    ) -> None:
        """Handle and log errors from LLM operations.

        Args:
            exc: The exception that occurred.
            operation: Description of the operation that failed.
            retryable: Whether the error may be transient.
        """
        if self._telemetry:
            self._telemetry.log(
                message=f"LLM {operation} failed: {exc}",
                level="ERROR",
                provider=self.provider_name,
                operation=operation,
                error_type=type(exc).__name__,
                retryable=retryable,
            )
