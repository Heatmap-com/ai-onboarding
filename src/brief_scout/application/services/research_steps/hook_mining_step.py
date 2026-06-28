"""Hook mining research step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models import HookMiningResult

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


class HookMiningStep:
    """Researches proven hooks, emotional/rational angles, and formats."""

    name = "hook_mining"
    output_schema = HookMiningResult

    def __init__(
        self,
        template: PromptTemplateConfig,
        llm: StructuredCompletionPort,
    ) -> None:
        """Initialize the step.

        Args:
            template: Prompt template for the hook mining step.
            llm: Narrow LLM port for structured completions.
        """
        self._template = template
        self._llm = llm

    async def execute(self, intake_data: IntakeData) -> HookMiningResult:
        """Execute the hook mining step."""
        from brief_scout.application.services.research_prompt_builder import (
            ResearchPromptBuilder,
        )

        prompt = ResearchPromptBuilder().build(
            self._template,
            {
                "brand_name": intake_data.brand_name,
                "target_customer": intake_data.target_customer,
                "primary_goal": intake_data.primary_goal,
            },
        )
        return await self._llm.complete_structured(prompt, HookMiningResult)
