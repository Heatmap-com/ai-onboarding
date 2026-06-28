"""Configuration adapter factory — creates ConfigurationPort instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.infrastructure.config.yaml_config_adapter import YAMLConfigAdapter

if TYPE_CHECKING:
    from pathlib import Path

    from brief_scout.domain.ports.config_port import ConfigurationPort
    from brief_scout.infrastructure.config.config_source import ConfigSource


class ConfigAdapterFactory:
    """Factory that constructs configuration adapters."""

    def create(
        self,
        config_dir: str | Path = "config",
        env: str | None = "development",
        source: ConfigSource | None = None,
    ) -> ConfigurationPort:
        """Create a configuration adapter.

        Args:
            config_dir: Directory containing YAML configuration files.
            env: Environment name for overlay selection.
            source: Optional ConfigSource.

        Returns:
            Instantiated ConfigurationPort implementation.
        """
        return YAMLConfigAdapter(
            config_dir=str(config_dir),
            env=env,
            source=source,
        )
