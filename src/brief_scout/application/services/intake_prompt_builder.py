"""Builds the extraction prompt for the intake use case."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from brief_scout.domain.models import IntakeData
from brief_scout.domain.ports import Prompt

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatMessage
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.application_ports import TemplateRenderer


class IntakePromptBuilder:
    """Builds prompts for structured intake data extraction."""

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        """Initialize with a template renderer.

        Args:
            renderer: Renderer for the system template. Defaults to Jinja2.
        """
        from brief_scout.application.services.template_renderer import (
            Jinja2TemplateRenderer,
        )

        self._renderer = renderer or Jinja2TemplateRenderer()

    def build_extraction_prompt(
        self,
        system_template: str,
        _journey: IntakeJourney,
        messages: list[ChatMessage],
    ) -> Prompt:
        """Build an extraction prompt from conversation history.

        Args:
            system_template: The system prompt template containing ``{{schema}}``.
            journey: Intake journey used to generate the JSON schema.
            messages: Full conversation history.

        Returns:
            A ``Prompt`` ready for structured completion.
        """
        schema = json.dumps(IntakeData.model_json_schema(), indent=2)
        system_prompt = self._renderer.render(system_template, {"schema": schema})

        transcript_lines: list[str] = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            transcript_lines.append(f"{prefix}: {msg.content}")
        transcript = "\n".join(transcript_lines)

        return Prompt(
            system=system_prompt,
            user=f"Extract structured data from this conversation:\n\n{transcript}",
        )
