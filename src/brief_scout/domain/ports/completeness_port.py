"""Completeness checker port — contract for intake completeness checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.services.completeness_checker import CompletenessResult


class CompletenessCheckPort(Protocol):
    """Narrow port for checking whether intake data is complete."""

    def check(self, intake_data: IntakeData) -> CompletenessResult:
        """Return the completeness result for the provided intake data."""
        ...
