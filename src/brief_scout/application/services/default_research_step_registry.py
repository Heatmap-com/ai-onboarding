"""Default research step registry — registers the built-in research steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.services.category_classifier import CategoryClassifier

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from brief_scout.application.services.research_steps import ResearchStep
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.ports.application_ports import StructuredCompletionPort


class DefaultResearchStepRegistry:
    """In-memory registry containing the five standard research steps.

    This is the Agent 1 default. Agent 2 can later replace it with a
    config-driven or plugin-based registry without changing
    ``ResearchUseCase``.
    """

    def __init__(
        self,
        prompts: Mapping[str, PromptTemplateConfig],
        llm: StructuredCompletionPort,
        classifier: CategoryClassifier | None = None,
    ) -> None:
        """Initialize the registry with prompt templates and LLM dependencies.

        Args:
            prompts: Mapping of step name to ``PromptTemplateConfig``.
                Expected keys: brand_audit, competitor_scan, trend_pulse,
                customer_voice, hook_mining.
            llm: Narrow LLM port for structured completions.
            classifier: Optional category classifier for steps that need it.
        """
        self._prompts = prompts
        self._llm = llm
        self._classifier = classifier or CategoryClassifier()

    @property
    def steps(self) -> Sequence[ResearchStep]:
        """Return the standard research steps in execution order."""
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

        return [
            BrandAuditStep(
                template=self._prompts["brand_audit"],
                llm=self._llm,
            ),
            CompetitorScanStep(
                template=self._prompts["competitor_scan"],
                llm=self._llm,
            ),
            TrendPulseStep(
                template=self._prompts["trend_pulse"],
                llm=self._llm,
                classifier=self._classifier,
            ),
            CustomerVoiceStep(
                template=self._prompts["customer_voice"],
                llm=self._llm,
                classifier=self._classifier,
            ),
            HookMiningStep(
                template=self._prompts["hook_mining"],
                llm=self._llm,
            ),
        ]
