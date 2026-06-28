"""Configuration Port — composite contract for configuration access.

This module now composes the narrow configuration ports:
  - AppConfigProvider
  - ProviderConfigSource
  - PromptTemplateProvider
  - ReloadableConfig

Adapters implementing ConfigurationPort must satisfy all four narrow
contracts. The composite remains convenient for composition-root wiring;
read-only clients should depend on the narrow ports instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import AppConfig, LLMProviderConfig, PromptTemplateConfig


class ConfigurationPort(Protocol):
    """Composite port for configuration loading and access.

    Implementations handle YAML parsing, environment variable
    interpolation, and deep merge of configuration overlays.

    This composite extends the narrow configuration ports. It is intended
    for composition-root wiring only; depend on AppConfigProvider,
    ProviderConfigSource, PromptTemplateProvider, or ReloadableConfig in
    application/domain code.
    """

    @property
    def app_config(self) -> AppConfig:
        """Return the validated application configuration."""
        ...

    def get_provider_config(self, provider_name: str) -> LLMProviderConfig:
        """Get configuration for a specific LLM provider."""
        ...

    def get_prompt_template(self, template_name: str) -> PromptTemplateConfig:
        """Get a prompt template by name.

        Raises:
            KeyError: If the template is not found.
        """
        ...

    def reload(self) -> None:
        """Reload configuration from source.

        The contract is eager: after this method returns, the next read
        must reflect the latest source state. Any source errors propagate
        as ConfigError or a subclass.
        """
        ...
