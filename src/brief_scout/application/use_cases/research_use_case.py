"""Research use case — orchestrates 5 parallel LLM research calls.

Per SPEC 6.2 — THE CORE PIPELINE. Executes 5 independent research calls
concurrently using asyncio.gather. Each call is isolated; failures in one
do not affect the others. The pipeline NEVER fails completely.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from brief_scout.domain.models import (
    BrandAuditResult,
    CompetitorScanResult,
    CustomerVoiceResult,
    HookMiningResult,
    IntakeData,
    ResearchBundle,
    TrendPulseResult,
)
from brief_scout.domain.ports import LogLevel, Prompt, TelemetryEvent

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.ports import ConfigurationPort, LLMPort, TelemetryPort

T = TypeVar("T", bound=BaseModel)


class ResearchUseCase:
    """Orchestrates the 5 parallel research calls.

    Uses ``asyncio.gather`` with ``return_exceptions=True`` for true
    parallelism. Each call is independent — a failure in any single call
    is logged and returns a default (empty) instance, allowing the pipeline
    to continue with partial results.

    Dependencies (constructor-injected):
        llm: LLM adapter for structured completions.
        config: Configuration source for prompt templates.
        telemetry: Telemetry adapter for logging and span tracking.
    """

    def __init__(
        self,
        llm: LLMPort,
        config: ConfigurationPort,
        telemetry: TelemetryPort,
    ) -> None:
        self._llm = llm
        self._config = config
        self._telemetry = telemetry

    async def execute(self, intake_data: IntakeData) -> ResearchBundle:
        """Execute 5 parallel research calls.

        Research calls:
            1. Brand Audit → BrandAuditResult
            2. Competitor Scan → CompetitorScanResult
            3. Trend Pulse → TrendPulseResult
            4. Customer Voice → CustomerVoiceResult
            5. Hook Mining → HookMiningResult

        All 5 run concurrently via ``asyncio.gather``. If any call fails,
        its result is the default (empty) model instance.

        Args:
            intake_data: Structured intake data collected from the user.

        Returns:
            ResearchBundle aggregating results from all 5 calls.
        """
        self._telemetry.log(
            "Starting research pipeline",
            level="INFO",
            brand_name=intake_data.brand_name,
        )
        span_id = self._telemetry.start_span("research.execute")

        # Launch all 5 research calls concurrently
        results = await asyncio.gather(
            self._call_brand_audit(intake_data),
            self._call_competitor_scan(intake_data),
            self._call_trend_pulse(intake_data),
            self._call_customer_voice(intake_data),
            self._call_hook_mining(intake_data),
            return_exceptions=True,
        )

        # Unpack results — exceptions are caught by _execute_single_research,
        # but we handle any residual exceptions defensively
        brand_audit = results[0] if isinstance(results[0], BrandAuditResult) else BrandAuditResult()
        competitor_scan = (
            results[1] if isinstance(results[1], CompetitorScanResult) else CompetitorScanResult()
        )
        trend_pulse = results[2] if isinstance(results[2], TrendPulseResult) else TrendPulseResult()
        customer_voice = (
            results[3] if isinstance(results[3], CustomerVoiceResult) else CustomerVoiceResult()
        )
        hook_mining = results[4] if isinstance(results[4], HookMiningResult) else HookMiningResult()

        bundle = ResearchBundle(
            brand_audit=brand_audit,
            competitor_scan=competitor_scan,
            trend_pulse=trend_pulse,
            customer_voice=customer_voice,
            hook_mining=hook_mining,
        )

        self._telemetry.log(
            "Research pipeline complete",
            level="INFO",
            brand_name=intake_data.brand_name,
        )
        self._telemetry.end_span(span_id)

        return bundle

    async def _call_brand_audit(
        self,
        intake_data: IntakeData,
    ) -> BrandAuditResult:
        """Call 1 — Brand Audit.

        Researches the brand's positioning, creative angle, key messages,
        visual identity, and recent campaigns.

        Args:
            intake_data: Structured intake data.

        Returns:
            BrandAuditResult with research findings.
        """
        prompts = self._config.app_config.prompts.research_brand_audit
        prompt = self._format_prompt(
            prompts,
            brand_name=intake_data.brand_name,
            brand_url=intake_data.brand_url,
        )
        return await self._execute_single_research(
            "Brand Audit",
            prompt,
            BrandAuditResult,
        )

    async def _call_competitor_scan(
        self,
        intake_data: IntakeData,
    ) -> CompetitorScanResult:
        """Call 2 — Competitor Ad Scan.

        Researches competitors' advertising strategies, creative patterns,
        and whitespace opportunities.

        Args:
            intake_data: Structured intake data.

        Returns:
            CompetitorScanResult with competitive landscape findings.
        """
        prompts = self._config.app_config.prompts.research_competitor_scan
        competitors_str = (
            ", ".join(intake_data.competitors) if intake_data.competitors else "unknown"
        )
        prompt = self._format_prompt(
            prompts,
            brand_name=intake_data.brand_name,
            competitors=competitors_str,
        )
        return await self._execute_single_research(
            "Competitor Scan",
            prompt,
            CompetitorScanResult,
        )

    async def _call_trend_pulse(
        self,
        intake_data: IntakeData,
    ) -> TrendPulseResult:
        """Call 3 — Category & Trend Pulse.

        Researches category trends, cultural moments, emerging angles,
        and timing notes.

        Args:
            intake_data: Structured intake data.

        Returns:
            TrendPulseResult with trend findings.
        """
        prompts = self._config.app_config.prompts.research_trend_pulse
        category = self._infer_category(intake_data)
        prompt = self._format_prompt(
            prompts,
            brand_name=intake_data.brand_name,
            category=category,
            primary_goal=intake_data.primary_goal,
        )
        return await self._execute_single_research(
            "Trend Pulse",
            prompt,
            TrendPulseResult,
        )

    async def _call_customer_voice(
        self,
        intake_data: IntakeData,
    ) -> CustomerVoiceResult:
        """Call 4 — Customer Voice.

        Researches customer language, desires, frustrations, emotional
        drivers, and objections.

        Args:
            intake_data: Structured intake data.

        Returns:
            CustomerVoiceResult with customer insight findings.
        """
        prompts = self._config.app_config.prompts.research_customer_voice
        category = self._infer_category(intake_data)
        prompt = self._format_prompt(
            prompts,
            brand_name=intake_data.brand_name,
            category=category,
            target_customer=intake_data.target_customer,
        )
        return await self._execute_single_research(
            "Customer Voice",
            prompt,
            CustomerVoiceResult,
        )

    async def _call_hook_mining(
        self,
        intake_data: IntakeData,
    ) -> HookMiningResult:
        """Call 5 — Hook & Angle Mining.

        Identifies proven hook types, emotional/rational angles, format
        recommendations, and headline starters.

        Args:
            intake_data: Structured intake data.

        Returns:
            HookMiningResult with hook and angle findings.
        """
        prompts = self._config.app_config.prompts.research_hook_mining
        prompt = self._format_prompt(
            prompts,
            brand_name=intake_data.brand_name,
            target_customer=intake_data.target_customer,
            primary_goal=intake_data.primary_goal,
        )
        return await self._execute_single_research(
            "Hook Mining",
            prompt,
            HookMiningResult,
        )

    async def _execute_single_research(
        self,
        call_name: str,
        prompt: Prompt,
        output_schema: type[T],
    ) -> T:
        """Execute a single research call with error handling and telemetry.

        Logs a start event, attempts the LLM structured completion, and
        returns either the parsed result or a default (empty) instance
        on failure.

        Args:
            call_name: Human-readable name for the research call.
            prompt: The formatted Prompt to send to the LLM.
            output_schema: Pydantic model class for the expected output.

        Returns:
            Parsed instance of ``output_schema``, or a default empty instance
            if the call fails.
        """
        self._telemetry.log(
            f"Research call starting: {call_name}",
            level="DEBUG",
            call_name=call_name,
        )
        span_id = self._telemetry.start_span(f"research.{call_name}")

        try:
            result: T = await self._llm.complete_structured(prompt, output_schema)
            self._telemetry.log(
                f"Research call complete: {call_name}",
                level="DEBUG",
                call_name=call_name,
            )
            self._telemetry.record_event(
                TelemetryEvent(
                    event_type="research.call.complete",
                    correlation_id=self._telemetry.get_correlation_id(),
                    data={"call_name": call_name, "status": "success"},
                    level=LogLevel.INFO,
                ),
            )
            return result
        except Exception as exc:
            self._telemetry.log(
                f"Research call failed: {call_name} — {exc}",
                level="ERROR",
                call_name=call_name,
                error=str(exc),
            )
            self._telemetry.record_event(
                TelemetryEvent(
                    event_type="research.call.failed",
                    correlation_id=self._telemetry.get_correlation_id(),
                    data={"call_name": call_name, "error": str(exc)},
                    level=LogLevel.ERROR,
                ),
            )
            return output_schema()
        finally:
            self._telemetry.end_span(span_id)

    @staticmethod
    def _format_prompt(
        template: PromptTemplateConfig,
        **kwargs: str,
    ) -> Prompt:
        """Format a prompt template with keyword substitution.

        Args:
            template: PromptTemplateConfig with system and user templates.
            **kwargs: Keyword substitutions for the user template.

        Returns:
            Formatted Prompt ready for the LLM.
        """
        user_content = template.user
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            user_content = user_content.replace(placeholder, value)
        return Prompt(
            system=template.system,
            user=user_content,
        )

    @staticmethod
    def _infer_category(intake_data: IntakeData) -> str:
        """Infer product category from intake data.

        Attempts to derive a category from the brand name, competitors,
        or target customer description.

        Args:
            intake_data: Structured intake data.

        Returns:
            Inferred category string.
        """
        brand = intake_data.brand_name.lower()
        competitors = " ".join(c.lower() for c in intake_data.competitors)
        target = intake_data.target_customer.lower()

        # Simple keyword-based inference
        keywords: dict[str, list[str]] = {
            "apparel / footwear": [
                "shoe",
                "shoes",
                "sneaker",
                "apparel",
                "clothing",
                "fashion",
                "wear",
                "footwear",
                "athletic",
                "sportswear",
            ],
            "technology / software": [
                "software",
                "app",
                "platform",
                "tech",
                "technology",
                "saas",
                "cloud",
                "ai",
                "digital",
            ],
            "food & beverage": [
                "food",
                "beverage",
                "drink",
                "restaurant",
                "coffee",
                "snack",
                "organic",
                "nutrition",
            ],
            "health & wellness": [
                "health",
                "wellness",
                "fitness",
                "gym",
                "supplement",
                "vitamin",
                "mental health",
                "wellbeing",
            ],
            "finance": [
                "finance",
                "banking",
                "investment",
                "crypto",
                "payment",
                "insurance",
                "fintech",
                "money",
            ],
        }

        combined_text = f"{brand} {competitors} {target}"
        for category, words in keywords.items():
            for word in words:
                if word in combined_text:
                    return category

        return "general"
