"""Intake data extractor port — contract for extracting structured intake values."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney


class IntakeDataExtractorPort(Protocol):
    """Narrow port for extracting structured intake data from a user message."""

    async def extract(
        self,
        user_message: str,
        current_intake: IntakeData,
        journey_definition: IntakeJourney,
    ) -> IntakeData:
        """Return a new IntakeData with values extracted from the user message."""
        ...
