"""Completion port — contract for generic text completion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import LLMResponse, Prompt

T = TypeVar("T", bound=BaseModel)


class CompletionPort(Protocol):
    """Narrow port for generic (unstructured) LLM completion."""

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

    @property
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            A string like 'fake', 'kimi', 'claude', 'openai'.
        """
        ...


class StructuredCompletionPort(Protocol):
    """Narrow port for structured LLM completion."""

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute LLM completion with structured output.

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
