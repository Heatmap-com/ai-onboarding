"""Research use case — thin coordinator over the research pipeline.

Per SPEC 6.2 — THE CORE PIPELINE. The actual orchestration now lives in
``ResearchPipeline``; this use case builds the default step sequence from
configuration and delegates execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.services.category_classifier import CategoryClassifier

if TYPE_CHECKING:
    from brief_scout.application.services.research_pipeline import ResearchPipeline
    from brief_scout.application.services.research_steps import ResearchStep
    from brief_scout.domain.models import IntakeData, ResearchBundle
    from brief_scout.domain.models.research import (
        BrandAuditResult,
        CompetitorScanResult,
        CustomerVoiceResult,
        HookMiningResult,
        TrendPulseResult,
    )
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort
    from brief_scout.domain.ports.config_port import ConfigurationPort
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class ResearchUseCase:
    """Thin coordinator that runs the configured research pipeline.

    Dependencies (constructor-injected):
        llm: Narrow LLM port for structured completions.
        config: Configuration source for prompt templates.
        telemetry: Telemetry adapter for logging and span tracking.
        classifier: Optional category classifier for steps that need it.
    """

    def __init__(
        self,
        llm: StructuredCompletionPort,
        config: ConfigurationPort,
        telemetry: TelemetryPort,
        classifier: CategoryClassifier | None = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._telemetry = telemetry
        self._classifier = classifier or CategoryClassifier()

    def _build_pipeline(self) -> ResearchPipeline:
        """Build the default research pipeline from configured steps."""
        from brief_scout.application.services.research_pipeline import ResearchPipeline
        from brief_scout.application.services.research_steps.brand_audit_step import (
            BrandAuditStep,
        )
        from brief_scout.application.services.research_steps.competitor_scan_step import (
            CompetitorScanStep,
        )
        from brief_scout.application.services.research_steps.customer_voice_step import (
            CustomerVoiceStep,
        )
        from brief_scout.application.services.research_steps.hook_mining_step import (
            HookMiningStep,
        )
        from brief_scout.application.services.research_steps.trend_pulse_step import (
            TrendPulseStep,
        )

        prompts = self._config.app_config.prompts.research_steps

        steps: list[ResearchStep] = [
            BrandAuditStep(template=prompts["brand_audit"], llm=self._llm),
            CompetitorScanStep(template=prompts["competitor_scan"], llm=self._llm),
            TrendPulseStep(
                template=prompts["trend_pulse"],
                llm=self._llm,
                classifier=self._classifier,
            ),
            CustomerVoiceStep(
                template=prompts["customer_voice"],
                llm=self._llm,
                classifier=self._classifier,
            ),
            HookMiningStep(template=prompts["hook_mining"], llm=self._llm),
        ]
        return ResearchPipeline(steps=steps, telemetry=self._telemetry)

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

    # -----------------------------------------------------------------------
    # Backward-compatible single-call helpers
    # -----------------------------------------------------------------------
    # ``routes.py`` (owned by Agent 2) still calls these private methods until
    # the integration branch wires the new pipeline. They are intentionally
    # thin wrappers around the same pluggable step classes.

    async def _call_brand_audit(self, intake_data: IntakeData) -> BrandAuditResult:
        """Call 1 — Brand Audit (deprecated, use ResearchPipeline)."""
        from brief_scout.application.services.research_steps.brand_audit_step import (
            BrandAuditStep,
        )

        prompts = self._config.app_config.prompts.research_steps
        step = BrandAuditStep(template=prompts["brand_audit"], llm=self._llm)
        return await step.execute(intake_data)

    async def _call_competitor_scan(self, intake_data: IntakeData) -> CompetitorScanResult:
        """Call 2 — Competitor Scan (deprecated, use ResearchPipeline)."""
        from brief_scout.application.services.research_steps.competitor_scan_step import (
            CompetitorScanStep,
        )

        prompts = self._config.app_config.prompts.research_steps
        step = CompetitorScanStep(template=prompts["competitor_scan"], llm=self._llm)
        return await step.execute(intake_data)

    async def _call_trend_pulse(self, intake_data: IntakeData) -> TrendPulseResult:
        """Call 3 — Trend Pulse (deprecated, use ResearchPipeline)."""
        from brief_scout.application.services.research_steps.trend_pulse_step import (
            TrendPulseStep,
        )

        prompts = self._config.app_config.prompts.research_steps
        step = TrendPulseStep(
            template=prompts["trend_pulse"],
            llm=self._llm,
            classifier=self._classifier,
        )
        return await step.execute(intake_data)

    async def _call_customer_voice(self, intake_data: IntakeData) -> CustomerVoiceResult:
        """Call 4 — Customer Voice (deprecated, use ResearchPipeline)."""
        from brief_scout.application.services.research_steps.customer_voice_step import (
            CustomerVoiceStep,
        )

        prompts = self._config.app_config.prompts.research_steps
        step = CustomerVoiceStep(
            template=prompts["customer_voice"],
            llm=self._llm,
            classifier=self._classifier,
        )
        return await step.execute(intake_data)

    async def _call_hook_mining(self, intake_data: IntakeData) -> HookMiningResult:
        """Call 5 — Hook Mining (deprecated, use ResearchPipeline)."""
        from brief_scout.application.services.research_steps.hook_mining_step import (
            HookMiningStep,
        )

        prompts = self._config.app_config.prompts.research_steps
        step = HookMiningStep(template=prompts["hook_mining"], llm=self._llm)
        return await step.execute(intake_data)
