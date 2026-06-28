"""App config provider port — read-only access to the validated AppConfig."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import AppConfig


class AppConfigProvider(Protocol):
    """Port for read-only access to the validated application configuration."""

    @property
    def app_config(self) -> AppConfig:
        """Return the validated application configuration.

        Returns:
            The root AppConfig Pydantic model with all settings validated.
        """
        ...
