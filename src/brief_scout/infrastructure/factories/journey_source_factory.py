"""Journey source factory — creates JourneySource instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.infrastructure.config.yaml_file_journey_source import (
    YamlFileJourneySource,
)

if TYPE_CHECKING:
    from pathlib import Path

    from brief_scout.domain.ports.journey_source_port import JourneySource


class JourneySourceFactory:
    """Factory that constructs journey sources."""

    def create(
        self,
        config_dir: str | Path = "config",
        env: str | None = None,
    ) -> JourneySource:
        """Create a journey source.

        Args:
            config_dir: Directory containing journey YAML files.
            env: Optional environment suffix.

        Returns:
            Instantiated JourneySource implementation.
        """
        return YamlFileJourneySource(config_dir=str(config_dir), env=env)
