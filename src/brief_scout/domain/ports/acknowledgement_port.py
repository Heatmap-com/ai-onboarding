"""Acknowledgement port — contract for intake acknowledgement generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney


class AcknowledgementPort(Protocol):
    """Narrow port for generating acknowledgement text for extracted values."""

    def generate(
        self,
        intake_data: IntakeData,
        journey_definition: IntakeJourney,
    ) -> str:
        """Return acknowledgement text summarizing collected values."""
        ...
