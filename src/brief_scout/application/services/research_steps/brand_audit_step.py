"""Brand audit research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import BrandAuditResult

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort
    from brief_scout.domain.ports.research_tool_port import ResearchTool


class BrandAuditStep:
    """Researches brand positioning, creative angles, and messaging."""

    name = "brand_audit"
    output_schema = BrandAuditResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
        search_tool: ResearchTool | None = None,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the brand audit step.
            llm: Narrow LLM port for structured completions.
            search_tool: Optional external search tool for grounding results.
        """
        self._template = template
        self._llm = llm
        self._search_tool = search_tool

    async def execute(self, intake_data: IntakeData) -> BrandAuditResult:
        """Execute the brand audit step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )
        from brief_scout.application.services.research_steps import _search_context

        search_results = await _search_context(
            self._search_tool,
            f"{intake_data.brand_name} brand positioning marketing",
        )
        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "brand_url": intake_data.brand_url,
                "search_results": search_results,
            },
        )
        result = await self._llm.complete_structured(prompt, BrandAuditResult)
        return result
