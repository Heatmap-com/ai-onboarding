"""YAML file loader — responsible only for file I/O and parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from brief_scout.domain.errors import ConfigError

if TYPE_CHECKING:
    from pathlib import Path


class YamlLoader:
    """Loads and parses individual YAML configuration files."""

    def load(self, path: Path) -> dict[str, Any]:
        """Load a YAML file into a dictionary.

        Args:
            path: Path to the YAML file.

        Returns:
            Parsed YAML content as a dictionary.

        Raises:
            ConfigError: If the file is missing or malformed.
        """
        if not path.exists():
            raise ConfigError(
                message=f"Configuration file not found: {path}",
                context={"file": str(path)},
            )

        try:
            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(
                message=f"Failed to parse {path.name}: {exc}",
                context={"file": str(path)},
            ) from exc

        if not isinstance(loaded, dict):
            raise ConfigError(
                message=f"Configuration file must contain a mapping: {path}",
                context={"file": str(path), "loaded_type": type(loaded).__name__},
            )

        return dict(loaded)
