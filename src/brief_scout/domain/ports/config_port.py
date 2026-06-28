"""Configuration Port — contract for configuration loading and access.

Adapters implementing this Protocol handle the mechanics of loading
configuration from files, environment variables, or remote sources.
The domain layer consumes configuration through this clean interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import AppConfig, LLMProviderConfig, PromptTemplateConfig


class ConfigurationPort(Protocol):
    """Port for configuration loading and access.

    Implementations handle YAML parsing, environment variable
    interpolation, and deep merge of configuration overlays.
    """

    @property
    def app_config(self) -> AppConfig:
        """Return the validated application configuration.

        Returns:
            The root AppConfig Pydantic model with all settings validated.
        """
        ...

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

    def get_prompt_template(self, template_name: str) -> PromptTemplateConfig:
        """Get a prompt template by name.

        Args:
            template_name: The template identifier (e.g., 'research_brand_audit').

        Returns:
            The PromptTemplateConfig with system and user strings.

        Raises:
            KeyError: If the template is not found.
        """
        ...

    def reload(self) -> None:
        """Reload configuration from source.

        Used for hot-reload scenarios where configuration files
        have changed and need to be re-read.
        """
        ...
