"""Journey source port — contract for loading the intake journey schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney


class JourneySource(Protocol):
    """Port for loading the declarative intake interview schema."""

    def load(self) -> IntakeJourney:
        """Load and return the intake journey configuration.

        Returns:
            An IntakeJourney instance.
        """
        ...
