"""Journey loader — reads the declarative intake schema from YAML.

The journey is intentionally loaded separately from the main application
configuration so that the interview flow can be edited in isolation.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from brief_scout.domain.models.journey import IntakeJourney


class JourneyLoader:
    """Loads an ``IntakeJourney`` from a YAML file.

    Looks for a top-level ``journey`` key by default. Supports environment
    overlays by merging a base ``journey.yaml`` with an optional
    ``journey.{env}.yaml`` file.

    Attributes:
        config_dir: Directory containing journey YAML files.
        env: Optional environment suffix (e.g., "demo").
    """

    def __init__(self, config_dir: str = "config", env: str | None = None) -> None:
        """Initialize the loader.

        Args:
            config_dir: Directory containing journey YAML files.
            env: Optional environment name. If provided, the loader attempts
                 to merge ``journey.{env}.yaml`` over ``journey.yaml``.
        """
        self._config_dir = Path(config_dir)
        self._env = env

    def load(self) -> IntakeJourney:
        """Load and validate the journey configuration.

        Returns:
            An ``IntakeJourney`` instance.

        Raises:
            FileNotFoundError: If the base journey file is missing.
            ValueError: If the YAML cannot be parsed or validated.
        """
        base_path = self._config_dir / "journey.yaml"
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
        """Deep-merge overlay over base.

        Dict values are merged recursively; lists and scalars are replaced.
        """
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
