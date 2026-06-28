"""LLM Port — primary contract for all LLM interactions.

Every LLM adapter (FakeLLMAdapter, KimiAdapter, ClaudeAdapter, etc.)
implements this Protocol. Domain and application layers depend only
on this interface, never on concrete adapter implementations.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """Standardized LLM response from any provider.

    Attributes:
        content: The raw text content of the response.
        model_used: The specific model that generated the response.
        provider: The provider identifier (e.g., 'fake', 'kimi', 'claude').
        tokens_used: Number of tokens consumed.
        latency_ms: Response latency in milliseconds.
        finish_reason: Why the response finished (e.g., 'stop', 'length').
        metadata: Additional provider-specific metadata.
    """

    content: str = ""
    model_used: str = ""
    provider: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0
    finish_reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Prompt(BaseModel):
    """Standardized prompt for LLM completion.

    Attributes:
        system: System-level instructions for the LLM.
        user: The user query or task description.
        context: Optional few-shot examples as list of dicts.
    """

    system: str = ""
    user: str = ""
    context: list[dict[str, str]] = Field(default_factory=list)


class LLMPort(Protocol):
    """Primary port for all LLM interactions.

    Every LLM adapter implements this Protocol. Use dependency injection
    to provide the appropriate adapter at application startup.
    """

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a single LLM completion.

        Args:
            prompt: The standardized prompt containing system and user messages.
            config: Optional provider-specific configuration overrides.

        Returns:
            An LLMResponse containing the generated content and metadata.
        """
        ...

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute LLM completion with structured output.

        The LLM is expected to return valid JSON that can be parsed
        into the provided Pydantic model.

        Args:
            prompt: The standardized prompt.
            output_schema: A Pydantic model class to parse the response into.
            config: Optional provider-specific configuration overrides.

        Returns:
            An instance of the output_schema Pydantic model.
        """
        ...

    @property
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            A string like 'fake', 'kimi', 'claude', 'openai'.
        """
        ...
