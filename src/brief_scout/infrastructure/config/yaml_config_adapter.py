"""YAML Config Adapter — loads and validates YAML configuration.

Supports environment variable interpolation (``${VAR_NAME}`` syntax),
deep merge of environment-specific overlays, and Pydantic validation.

Typical usage::

    adapter = YAMLConfigAdapter(config_dir="config", env="development")
    config = adapter.app_config  # Validated AppConfig instance
    provider_cfg = adapter.get_provider_config("fake")

Configuration loading order:
1. Load ``{config_dir}/default.yaml``
2. Load ``{config_dir}/{env}.yaml`` if it exists
3. Interpolate ``${ENV_VAR}`` placeholders
4. Deep merge overlays onto defaults
5. Validate with Pydantic AppConfig
"""

from __future__ import annotations

import os
import re
from functools import cached_property
from pathlib import Path
from typing import Any, cast

import yaml

from brief_scout.domain.errors import ConfigError
from brief_scout.domain.models.config import (
    AppConfig,
    LLMProviderConfig,
    PromptTemplateConfig,
)


class YAMLConfigAdapter:
    """Loads and validates YAML configuration with Pydantic schemas.

    Supports environment variable interpolation (``${VAR_NAME}``) and
    deep merge of environment-specific overlays.

    Attributes:
        config_dir: Directory containing YAML configuration files.
        env: Environment name (e.g., 'development', 'production').
    """

    _ENV_VAR_PATTERN: re.Pattern[str] = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, config_dir: str = "config", env: str = "development") -> None:
        """Initialize the YAML config adapter.

        Args:
            config_dir: Directory containing ``default.yaml`` and
                        environment-specific override files.
            env: Environment name used to select the overlay file
                 (e.g., ``development`` loads ``{config_dir}/development.yaml``).
        """
        self._config_dir = Path(config_dir)
        self._env = env
        self._raw_config: dict[str, Any] | None = None

    @cached_property
    def app_config(self) -> AppConfig:
        """Load, merge, and validate the full application configuration.

        Loads ``default.yaml``, applies environment-specific overlays,
        interpolates environment variables, and validates with Pydantic.

        Returns:
            A validated AppConfig instance.

        Raises:
            ConfigError: If configuration files cannot be loaded or validated.
        """
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
        """Get configuration for a specific LLM provider.

        Args:
            provider_name: The provider identifier (e.g., 'fake', 'openai').

        Returns:
            The LLMProviderConfig for the named provider.

        Raises:
            KeyError: If the provider is not configured.
        """
        if self._raw_config is None:
            _ = self.app_config  # Trigger loading

        providers = (self._raw_config or {}).get("llm_providers", {})
        if provider_name not in providers:
            raise KeyError(f"LLM provider '{provider_name}' not configured")

        return LLMProviderConfig.model_validate(providers[provider_name])

    def get_prompt_template(self, template_name: str) -> PromptTemplateConfig:
        """Get a prompt template by name.

        Looks up the template in the ``prompts`` section of the configuration.
        Template names map to keys in the prompts dictionary (e.g.,
        ``research_brand_audit``).

        Args:
            template_name: The template identifier.

        Returns:
            A PromptTemplateConfig with system and user strings.

        Raises:
            KeyError: If the template is not found.
        """
        if self._raw_config is None:
            _ = self.app_config  # Trigger loading

        prompts = (self._raw_config or {}).get("prompts", {})
        if template_name not in prompts:
            raise KeyError(f"Prompt template '{template_name}' not found")

        template_data = prompts[template_name]
        if isinstance(template_data, dict):
            return PromptTemplateConfig.model_validate(template_data)

        # Handle simple string values
        return PromptTemplateConfig()

    def reload(self) -> None:
        """Reload configuration from source.

        Clears cached state and forces re-reading of all configuration
        files on the next access to ``app_config``.
        """
        self._raw_config = None
        # Clear the cached_property cache
        if "app_config" in self.__dict__:
            del self.__dict__["app_config"]

    def _load_raw(self) -> dict[str, Any]:
        """Load and merge raw configuration from YAML files.

        Returns:
            A merged dictionary of configuration values.

        Raises:
            ConfigError: If required files are missing or malformed.
        """
        # Load default.yaml
        default_path = self._config_dir / "default.yaml"
        if not default_path.exists():
            raise ConfigError(
                message=f"Default configuration not found: {default_path}",
                context={"config_dir": str(self._config_dir)},
            )

        try:
            with open(default_path, encoding="utf-8") as f:
                default_raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(
                message=f"Failed to parse default.yaml: {exc}",
                context={"file": str(default_path)},
            ) from exc

        # Load environment overlay
        env_path = self._config_dir / f"{self._env}.yaml"
        if env_path.exists():
            try:
                with open(env_path, encoding="utf-8") as f:
                    env_raw = yaml.safe_load(f) or {}
            except yaml.YAMLError as exc:
                raise ConfigError(
                    message=f"Failed to parse {env_path.name}: {exc}",
                    context={"file": str(env_path)},
                ) from exc

            # Deep merge env onto default
            default_raw = self._deep_merge(default_raw, env_raw)

        # Interpolate environment variables
        default_raw = self._interpolate_env_vars(default_raw)

        return cast("dict[str, Any]", default_raw)

    def _deep_merge(
        self,
        base: dict[str, Any],
        overlay: dict[str, Any],
    ) -> dict[str, Any]:
        """Recursively merge overlay dictionary onto base.

        For each key in overlay:
        - If both values are dicts, merge recursively.
        - Otherwise, overlay value replaces base value.

        Args:
            base: The base dictionary (default config).
            overlay: The overlay dictionary (env-specific overrides).

        Returns:
            A new dictionary with merged values.
        """
        result = dict(base)
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _interpolate_env_vars(self, obj: Any) -> Any:
        """Recursively interpolate ``${VAR_NAME}`` placeholders with env vars.

        Walks through strings, lists, and dictionaries, replacing any
        ``${VAR_NAME}`` pattern with the corresponding environment variable
        value. If the variable is not set, the placeholder is left unchanged.

        Args:
            obj: The object to interpolate (str, list, dict, or other).

        Returns:
            The interpolated object with the same structure.
        """
        if isinstance(obj, str):
            return self._replace_env_vars(obj)
        elif isinstance(obj, dict):
            return {k: self._interpolate_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._interpolate_env_vars(item) for item in obj]
        return obj

    def _replace_env_vars(self, text: str) -> str:
        """Replace ``${VAR_NAME}`` patterns in a string with env var values.

        Args:
            text: The string potentially containing placeholders.

        Returns:
            The string with placeholders replaced by environment variable
            values (or left unchanged if the variable is not set).
        """

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return self._ENV_VAR_PATTERN.sub(replacer, text)
