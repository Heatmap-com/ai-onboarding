"""Competitor scan research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import CompetitorScanResult

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


class CompetitorScanStep:
    """Researches competitor advertising strategies and whitespace."""

    name = "competitor_scan"
    output_schema = CompetitorScanResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the competitor scan step.
            llm: Narrow LLM port for structured completions.
        """
        self._template = template
        self._llm = llm

    async def execute(self, intake_data: IntakeData) -> CompetitorScanResult:
        """Execute the competitor scan step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )

        competitors_str = (
            ", ".join(intake_data.competitors) if intake_data.competitors else "unknown"
        )
        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "competitors": competitors_str,
            },
        )
        return await self._llm.complete_structured(prompt, CompetitorScanResult)
