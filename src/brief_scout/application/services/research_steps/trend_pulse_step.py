"""Trend pulse research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import TrendPulseResult
from brief_scout.domain.services.category_classifier import CategoryClassifier

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort
    from brief_scout.domain.ports.research_tool_port import ResearchTool


class TrendPulseStep:
    """Researches category trends, cultural moments, and emerging angles."""

    name = "trend_pulse"
    output_schema = TrendPulseResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
        classifier: CategoryClassifier | None = None,
        search_tool: ResearchTool | None = None,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the trend pulse step.
            llm: Narrow LLM port for structured completions.
            classifier: Optional category classifier.
            search_tool: Optional external search tool for grounding results.
        """
        self._template = template
        self._llm = llm
        self._classifier = classifier or CategoryClassifier()
        self._search_tool = search_tool

    async def execute(self, intake_data: IntakeData) -> TrendPulseResult:
        """Execute the trend pulse step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )
        from brief_scout.application.services.research_steps import _search_context

        category = await self._classifier.classify(intake_data)
        search_results = await _search_context(
            self._search_tool,
            f"{intake_data.brand_name} {category} trends",
        )
        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "category": category,
                "primary_goal": intake_data.primary_goal,
                "search_results": search_results,
            },
        )
        return await self._llm.complete_structured(prompt, TrendPulseResult)
