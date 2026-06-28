"""Brand audit research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import BrandAuditResult

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


class BrandAuditStep:
    """Researches brand positioning, creative angles, and messaging."""

    name = "brand_audit"
    output_schema = BrandAuditResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the brand audit step.
            llm: Narrow LLM port for structured completions.
        """
        self._template = template
        self._llm = llm

    async def execute(self, intake_data: IntakeData) -> BrandAuditResult:
        """Execute the brand audit step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )

        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "brand_url": intake_data.brand_url,
            },
        )
        result = await self._llm.complete_structured(prompt, BrandAuditResult)
        return result
