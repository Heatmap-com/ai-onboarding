"""Research pipeline — orchestrates registered research steps.

This is a compatibility stub that bridges the current ResearchUseCase
with the streaming pipeline contract expected by the interface layer.
Agent 1 will replace it with a step-registry based implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from brief_scout.application.use_cases.research_use_case import ResearchUseCase
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.research import ResearchBundle


class PipelineEvent(BaseModel):
    """Domain event emitted by a pipeline stage."""

    stage: str = ""
    status: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ResearchStep(Protocol):
    """Protocol for a single research step."""

    name: str

    async def execute(self, intake_data: IntakeData) -> BaseModel:
        """Execute the step and return a typed result."""
        ...


class ResearchPipeline:
    """Orchestrates research steps and emits progress events.

    Args:
        steps: Sequence of research step implementations (unused in stub).
        research_use_case: The current ResearchUseCase that runs all calls.
    """

    def __init__(
        self,
        steps: Sequence[ResearchStep],
        research_use_case: ResearchUseCase,
    ) -> None:
        self._steps = list(steps)
        self._research_use_case = research_use_case

    async def execute(self, intake_data: IntakeData) -> ResearchBundle:
        """Execute all research steps and return a ResearchBundle."""
        return await self._research_use_case.execute(intake_data)

    async def stream(
        self,
        intake_data: IntakeData,
    ) -> AsyncIterator[PipelineEvent]:
        """Stream research progress events.

        The current ResearchUseCase executes all calls concurrently, so this
        stub yields a "started" event, runs the bundle, then yields a
        "complete" event for each predefined research area.
        """
        yield PipelineEvent(
            stage="research",
            status="started",
            payload={
                "steps": [
                    "Brand Audit",
                    "Competitor Scan",
                    "Trend Pulse",
                    "Customer Voice",
                    "Hook Mining",
                ],
            },
        )

        bundle = await self.execute(intake_data)

        step_results = [
            ("Brand Audit", bundle.brand_audit),
            ("Competitor Scan", bundle.competitor_scan),
            ("Trend Pulse", bundle.trend_pulse),
            ("Customer Voice", bundle.customer_voice),
            ("Hook Mining", bundle.hook_mining),
        ]
        for name, result in step_results:
            yield PipelineEvent(
                stage="research_step",
                status="complete",
                payload={"name": name, "status": "complete", "has_data": bool(result)},
            )

        yield PipelineEvent(
            stage="research",
            status="complete",
            payload={},
        )
