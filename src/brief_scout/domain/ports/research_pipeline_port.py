"""Research pipeline port — narrow contract for research execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.research import ResearchBundle
    from brief_scout.domain.ports.pipeline_event import PipelineEvent


class ResearchPipelinePort(Protocol):
    """Narrow port for executing research and producing a research bundle."""

    async def execute(self, intake_data: IntakeData) -> ResearchBundle:
        """Execute research for the given intake data."""
        ...

    def stream(
        self,
        intake_data: IntakeData,
    ) -> AsyncIterator[PipelineEvent]:
        """Execute research steps concurrently, yielding progress events."""
        ...

    @property
    def last_bundle(self) -> ResearchBundle | None:
        """The bundle produced by the most recent stream/execute call."""
        ...
