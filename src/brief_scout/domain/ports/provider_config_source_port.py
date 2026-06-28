"""Provider config source port — lookup for LLM provider configurations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import LLMProviderConfig


class ProviderConfigSource(Protocol):
    """Port for retrieving LLM provider configurations by name."""

    def get_provider_config(self, provider_name: str) -> LLMProviderConfig:
        """Get configuration for a specific LLM provider.

        Args:
            provider_name: The provider identifier (e.g., 'fake', 'openai').

        Returns:
            The LLMProviderConfig for the named provider.

        Raises:
            KeyError: If the provider is not configured.
        """
        ...
