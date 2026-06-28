"""YAML Config Adapter — coordinates loading and validation of YAML configuration.

Responsibilities:
  - Coordinate a ConfigSource to load raw configuration.
  - Validate raw configuration with Pydantic AppConfig.
  - Cache the validated config.
  - Provide typed accessors for provider configs and prompt templates.

The actual file I/O, deep merge, and env interpolation have been extracted
into YamlLoader, ConfigMerger, and EnvInterpolator.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brief_scout.domain.errors import ConfigError
from brief_scout.domain.models.config import (
    AppConfig,
    LLMProviderConfig,
    PromptTemplateConfig,
)

if TYPE_CHECKING:
    from brief_scout.infrastructure.config.config_source import ConfigSource


class YAMLConfigAdapter:
    """Loads and validates YAML configuration with Pydantic schemas."""

    def __init__(
        self,
        config_dir: str | Path = "config",
        env: str | None = "development",
        source: ConfigSource | None = None,
    ) -> None:
        """Initialize the YAML config adapter.

        Args:
            config_dir: Directory containing YAML configuration files.
            env: Environment name used to select the overlay file.
            source: Optional ConfigSource. If omitted, a YamlFileConfigSource
                is constructed from config_dir and env.
        """
        self._config_dir = Path(config_dir)
        self._env = env
        self._source = source
        self._raw_config: dict[str, Any] | None = None

    @cached_property
    def app_config(self) -> AppConfig:
        """Load, merge, and validate the full application configuration."""
        raw = self._load_raw()
        self._raw_config = raw

        try:
            return AppConfig.model_validate(raw)
        except Exception as exc:
            raise ConfigError(
                message=f"Failed to validate application configuration: {exc}",
                context={"raw_config_keys": list(raw.keys())},
            ) from exc

    def get_provider_config(self, provider_name: str) -> LLMProviderConfig:
        """Get configuration for a specific LLM provider."""
        if self._raw_config is None:
            _ = self.app_config  # Trigger loading

        providers = (self._raw_config or {}).get("llm_providers", {})
        if provider_name not in providers:
            raise KeyError(f"LLM provider '{provider_name}' not configured")

        return LLMProviderConfig.model_validate(providers[provider_name])

    def get_prompt_template(self, template_name: str) -> PromptTemplateConfig:
        """Get a prompt template by name.

        Raises:
            KeyError: If the template is not found.
            ConfigError: If the template value is ambiguous.
        """
        if self._raw_config is None:
            _ = self.app_config  # Trigger loading

        prompts = (self._raw_config or {}).get("prompts", {})
        if template_name not in prompts:
            raise KeyError(f"Prompt template '{template_name}' not found")

        template_data = prompts[template_name]
        if isinstance(template_data, dict):
            return PromptTemplateConfig.model_validate(template_data)

        if isinstance(template_data, str):
            # String-valued templates are treated as the user message.
            return PromptTemplateConfig(system="", user=template_data)

        raise ConfigError(
            message=f"Prompt template '{template_name}' has unsupported type",
            context={"template_type": type(template_data).__name__},
        )

    def reload(self) -> None:
        """Reload configuration from source.

        Eager contract: clears cached state so the next access re-reads source.
        """
        self._raw_config = None
        if "app_config" in self.__dict__:
            del self.__dict__["app_config"]

    def _load_raw(self) -> dict[str, Any]:
        """Load raw configuration via the configured source."""
        if self._source is None:
            from brief_scout.infrastructure.config.config_source import (
                YamlFileConfigSource,
            )

            self._source = YamlFileConfigSource(
                config_dir=self._config_dir,
                env=self._env,
            )
        return self._source.load()
