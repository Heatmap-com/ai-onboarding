"""YAML file journey source — loads the intake journey from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from brief_scout.domain.models.journey import IntakeJourney

if TYPE_CHECKING:
    from brief_scout.infrastructure.config.config_merger import ConfigMerger


class YamlFileJourneySource:
    """Loads an IntakeJourney from a YAML source.

    Supports environment overlays by merging a base journey.yaml with an
    optional journey.{env}.yaml file.
    """

    def __init__(
        self,
        config_dir: str | Path = "config",
        env: str | None = None,
        base_name: str = "journey.yaml",
        merger: ConfigMerger | None = None,
    ) -> None:
        """Initialize the journey source.

        Args:
            config_dir: Directory containing journey YAML files.
            env: Optional environment suffix.
            base_name: Base journey file name.
            merger: ConfigMerger for overlay merging.
        """
        self._config_dir = Path(config_dir)
        self._env = env
        self._base_name = base_name
        self._merger = merger

    def load(self) -> IntakeJourney:
        """Load and validate the journey configuration."""
        base_path = self._config_dir / self._base_name
        if not base_path.exists():
            raise FileNotFoundError(f"Journey configuration not found: {base_path}")

        data = self._load_yaml(base_path)

        if self._env:
            env_path = self._config_dir / f"journey.{self._env}.yaml"
            if env_path.exists():
                env_data = self._load_yaml(env_path)
                data = self._merge(data, env_data)

        journey_data = data.get("journey")
        if not isinstance(journey_data, dict):
            journey_data = {}
        return IntakeJourney(**journey_data)

    def _load_yaml(self, path: Path) -> dict[str, object]:
        """Load a YAML file into a dictionary."""
        with path.open(encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        return loaded if isinstance(loaded, dict) else {}

    def _merge(
        self,
        base: dict[str, object],
        overlay: dict[str, object],
    ) -> dict[str, object]:
        """Deep-merge overlay over base."""
        if self._merger is not None:
            return self._merger.merge(base, overlay)

        merged: dict[str, object] = {}
        for key in set(base) | set(overlay):
            base_value = base.get(key)
            overlay_value = overlay.get(key)
            if isinstance(base_value, dict) and isinstance(overlay_value, dict):
                merged[key] = self._merge(base_value, overlay_value)
            elif overlay_value is not None:
                merged[key] = overlay_value
            else:
                merged[key] = base_value
        return merged
