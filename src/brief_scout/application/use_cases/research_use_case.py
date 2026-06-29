"""Research use case — thin coordinator over the research pipeline.

Per SPEC 6.2 — THE CORE PIPELINE. The actual orchestration lives in
``ResearchPipeline``; this use case builds the default step sequence from
a ``ResearchStepRegistry`` and delegates execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.application.services.research_pipeline import ResearchPipeline
    from brief_scout.domain.models import IntakeData, ResearchBundle
    from brief_scout.domain.ports.research_step_registry_port import (
        ResearchStepRegistry,
    )
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class ResearchUseCase:
    """Thin coordinator that runs the configured research pipeline.

    Dependencies (constructor-injected):
        registry: Source of ordered research steps.
        telemetry: Telemetry adapter for logging and span tracking.
    """

    def __init__(
        self,
        registry: ResearchStepRegistry,
        telemetry: TelemetryPort,
        max_concurrent_calls: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._registry = registry
        self._telemetry = telemetry
        self._max_concurrent_calls = max_concurrent_calls
        self._timeout_seconds = timeout_seconds

    def build_pipeline(self) -> ResearchPipeline:
        """Build the default research pipeline from the configured registry."""
        from brief_scout.application.services.research_pipeline import ResearchPipeline

        return ResearchPipeline(
            steps=list(self._registry.steps),
            telemetry=self._telemetry,
            max_concurrent_calls=self._max_concurrent_calls,
            timeout_seconds=self._timeout_seconds,
        )

    # Backwards-compatible alias for tests and callers still using the old name.
    _build_pipeline = build_pipeline

    async def execute(self, intake_data: IntakeData) -> ResearchBundle:
        """Execute the configured research pipeline.

        Args:
            intake_data: Structured intake data collected from the user.

        Returns:
            ResearchBundle aggregating results from all configured steps.
        """
        self._telemetry.log(
            "Starting research pipeline",
            level="INFO",
            brand_name=intake_data.brand_name,
        )
        span_id = self._telemetry.start_span("research.execute")

        try:
            pipeline = self._build_pipeline()
            bundle = await pipeline.execute(intake_data)
            self._telemetry.log(
                "Research pipeline complete",
                level="INFO",
                brand_name=intake_data.brand_name,
            )
            return bundle
        finally:
            self._telemetry.end_span(span_id)
