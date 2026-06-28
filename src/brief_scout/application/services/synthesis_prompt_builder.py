"""Builds the synthesis prompt from intake data and research results."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from brief_scout.domain.ports import Prompt

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.research import ResearchBundle


class SynthesisPromptBuilder:
    """Builds the synthesis prompt for converting research into a Brief."""

    def build(
        self,
        template: PromptTemplateConfig,
        intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> Prompt:
        """Return a synthesis prompt with serialized intake and research JSON.

        Args:
            template: The synthesis prompt template.
            intake_data: Collected intake data.
            research_bundle: Aggregated research results.

        Returns:
            A formatted ``Prompt``.
        """
        intake_json = json.dumps(
            intake_data.model_dump(),
            indent=2,
            default=str,
        )
        research_json = json.dumps(
            research_bundle.model_dump(),
            indent=2,
            default=str,
        )

        user_content = template.user.replace("{intake_json}", intake_json)
        user_content = user_content.replace("{research_json}", research_json)

        return Prompt(
            system=template.system,
            user=user_content,
        )
