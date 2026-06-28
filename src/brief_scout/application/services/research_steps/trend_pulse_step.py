"""Trend pulse research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import TrendPulseResult
from brief_scout.domain.services.category_classifier import CategoryClassifier

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


class TrendPulseStep:
    """Researches category trends, cultural moments, and emerging angles."""

    name = "trend_pulse"
    output_schema = TrendPulseResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
        classifier: CategoryClassifier | None = None,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the trend pulse step.
            llm: Narrow LLM port for structured completions.
            classifier: Optional category classifier.
        """
        self._template = template
        self._llm = llm
        self._classifier = classifier or CategoryClassifier()

    async def execute(self, intake_data: IntakeData) -> TrendPulseResult:
        """Execute the trend pulse step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )

        category = self._classifier.classify(intake_data)
        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "category": category,
                "primary_goal": intake_data.primary_goal,
            },
        )
        return await self._llm.complete_structured(prompt, TrendPulseResult)
