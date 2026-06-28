"""Synthesis use case — combines intake data + research into a Brief.

Per SPEC 6.3 — Single LLM call that takes all inputs (structured intake
and research bundle) and produces a complete, structured Brief model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.errors import BriefScoutError, SynthesisError
from brief_scout.domain.models import Brief, IntakeData, ResearchBundle
from brief_scout.domain.ports.telemetry_port import LogLevel, TelemetryEvent

if TYPE_CHECKING:
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort
    from brief_scout.domain.ports.config_port import ConfigurationPort
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class SynthesisUseCase:
    """Synthesizes research results + intake data into a complete Brief.

    Performs a single structured LLM call that takes the full intake data
    and all research results as JSON context, producing a populated Brief
    model with creative angles, headlines, hooks, and strategic direction.

    Dependencies (constructor-injected):
        llm: Narrow LLM port for structured completions.
        config: Configuration source for the synthesis prompt template.
        telemetry: Telemetry adapter for logging and span tracking.
    """

    def __init__(
        self,
        llm: StructuredCompletionPort,
        config: ConfigurationPort,
        telemetry: TelemetryPort,
    ) -> None:
        self._llm = llm
        self._config = config
        self._telemetry = telemetry

    async def execute(
        self,
        intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> Brief:
        """Synthesize intake + research into a Brief.

        Steps:
            1. Format the synthesis prompt with intake and research JSON.
            2. Call LLM with structured output (Brief schema).
            3. Attach sources (ResearchBundle) to the brief.
            4. Return the populated Brief.

        Args:
            intake_data: Structured intake data from the user conversation.
            research_bundle: Aggregated results from research pipeline.

        Returns:
            A fully populated Brief model.

        Raises:
            SynthesisError: If the LLM call or parsing fails.
        """
        self._telemetry.log(
            "Starting brief synthesis",
            level="INFO",
            brand_name=intake_data.brand_name,
        )
        span_id = self._telemetry.start_span("synthesis.execute")

        try:
            from brief_scout.application.services.synthesis_prompt_builder import (
                SynthesisPromptBuilder,
            )

            prompt = SynthesisPromptBuilder().build(
                self._config.app_config.prompts.synthesis,
                intake_data,
                research_bundle,
            )

            brief: Brief = await self._llm.complete_structured(prompt, Brief)
            brief.sources = research_bundle

            self._telemetry.log(
                "Brief synthesis complete",
                level="INFO",
                brand_name=brief.brand_name,
                creative_angles_count=len(brief.creative_angles),
            )
            self._telemetry.record_event(
                TelemetryEvent(
                    event_type="synthesis.complete",
                    correlation_id=self._telemetry.get_correlation_id(),
                    data={
                        "brand_name": brief.brand_name,
                        "has_creative_angles": len(brief.creative_angles) > 0,
                        "has_sample_headlines": len(brief.sample_headlines) > 0,
                    },
                    level=LogLevel.INFO,
                ),
            )

            return brief

        except BriefScoutError:
            raise
        except Exception as exc:
            self._telemetry.log(
                f"Brief synthesis failed: {exc}",
                level="ERROR",
                error=str(exc),
            )
            raise SynthesisError(
                message=f"Failed to synthesize brief: {exc}",
            ) from exc
        finally:
            self._telemetry.end_span(span_id)
