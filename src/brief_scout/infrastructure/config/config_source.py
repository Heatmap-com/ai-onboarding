"""Config source abstraction — decouples adapter from file naming/layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

from brief_scout.infrastructure.config.config_merger import ConfigMerger
from brief_scout.infrastructure.config.env_interpolator import EnvInterpolator
from brief_scout.infrastructure.config.yaml_loader import YamlLoader


class ConfigSource(Protocol):
    """Source of raw configuration data."""

    def load(self) -> dict[str, Any]:
        """Load and return raw configuration as a dictionary."""
        ...


class YamlFileConfigSource:
    """Loads configuration from default + optional environment YAML files."""

    def __init__(
        self,
        config_dir: str | Path,
        env: str | None = None,
        loader: YamlLoader | None = None,
        merger: ConfigMerger | None = None,
        interpolator: EnvInterpolator | None = None,
    ) -> None:
        """Initialize the YAML file config source.

        Args:
            config_dir: Directory containing YAML configuration files.
            env: Optional environment name for an overlay file.
            loader: YamlLoader instance.
            merger: ConfigMerger instance.
            interpolator: EnvInterpolator instance.
        """
        self._config_dir = Path(config_dir)
        self._env = env
        self._loader = loader or YamlLoader()
        self._merger = merger or ConfigMerger()
        self._interpolator = interpolator or EnvInterpolator()

    def load(self) -> dict[str, Any]:
        """Load default + env overlay YAML files with interpolation."""
        default_path = self._config_dir / "default.yaml"
        raw = self._loader.load(default_path)

        if self._env:
            env_path = self._config_dir / f"{self._env}.yaml"
            if env_path.exists():
                env_raw = self._loader.load(env_path)
                raw = self._merger.merge(raw, env_raw)

        return cast("dict[str, Any]", self._interpolator.interpolate(raw))
