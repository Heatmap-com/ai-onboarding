"""Journey loader — thin wrapper around a JourneySource."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from brief_scout.infrastructure.config.yaml_file_journey_source import (
    YamlFileJourneySource,
)

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.journey_source_port import JourneySource


class JourneyLoader:
    """Loads an ``IntakeJourney`` from a configured ``JourneySource``.

    Attributes:
        config_dir: Directory containing journey YAML files.
        env: Optional environment suffix.
    """

    def __init__(
        self,
        config_dir: str = "config",
        env: str | None = None,
        source: JourneySource | None = None,
    ) -> None:
        """Initialize the loader.

        Args:
            config_dir: Directory containing journey YAML files.
            env: Optional environment name for overlay merging.
            source: Optional JourneySource. If omitted, a YamlFileJourneySource
                is constructed from config_dir and env.
        """
        self._config_dir = Path(config_dir)
        self._env = env
        self._source = source

    def load(self) -> IntakeJourney:
        """Load and validate the journey configuration."""
        if self._source is None:
            self._source = YamlFileJourneySource(
                config_dir=self._config_dir,
                env=self._env,
            )
        return self._source.load()
