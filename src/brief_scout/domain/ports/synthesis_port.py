"""Synthesis port — narrow contract for brief synthesis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.research import ResearchBundle


class SynthesisPort(Protocol):
    """Narrow port for synthesizing a brief from intake and research data."""

    async def execute(
        self,
        intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> Brief:
        """Synthesize and return the populated brief."""
        ...
