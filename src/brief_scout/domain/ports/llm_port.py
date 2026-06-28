"""LLM Port — composite contract for all LLM interactions.

This module now composes the narrow LLM ports:
  - CompletionPort
  - StructuredCompletionPort

Every full LLM adapter implements this composite. Application code should
depend on CompletionPort or StructuredCompletionPort as appropriate.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel):
    """A single message in the prompt context.

    Attributes:
        role: Message role, e.g. 'system', 'user', 'assistant'.
        content: Message text content.
    """

    role: str = "user"
    content: str = ""


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
        context: Optional few-shot examples as list of ChatMessages.
    """

    system: str = ""
    user: str = ""
    context: list[ChatMessage] = Field(default_factory=list)

    @field_validator("context", mode="before")
    @classmethod
    def _normalize_context(
        cls,
        value: list[ChatMessage] | list[dict[str, str]] | None,
    ) -> list[ChatMessage]:
        """Accept either ChatMessage objects or legacy dicts for compatibility."""
        if value is None:
            return []
        normalized: list[ChatMessage] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(ChatMessage(**item))
            else:
                normalized.append(item)
        return normalized


class LLMPort(Protocol):
    """Composite port for all LLM interactions.

    Every LLM adapter implements this Protocol. Use dependency injection
    to provide the appropriate adapter at application startup.

    This composite extends CompletionPort and StructuredCompletionPort.
    """

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a single LLM completion."""
        ...

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute LLM completion with structured output."""
        ...

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        ...
