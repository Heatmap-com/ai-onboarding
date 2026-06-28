"""Intake data differ — detects which journey fields changed state this turn."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney


class IntakeDataDiffer:
    """Compare two ``IntakeData`` snapshots and report newly populated fields."""

    def __init__(self, journey: IntakeJourney) -> None:
        """Initialize with the intake journey schema."""
        self._journey = journey

    def newly_filled_fields(
        self,
        previous: IntakeData,
        current: IntakeData,
    ) -> list[str]:
        """Return field names that went from empty to populated.

        Args:
            previous: Snapshot before the latest user message was processed.
            current: Snapshot after merging extracted data.

        Returns:
            Ordered list of field names newly populated this turn.
        """
        names: list[str] = []
        for field in self._journey.fields:
            previous_value = getattr(previous, field.name)
            current_value = getattr(current, field.name)
            if field.is_empty(previous_value) and not field.is_empty(current_value):
                names.append(field.name)
        return names
