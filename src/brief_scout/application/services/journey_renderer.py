"""JourneyRenderer — renders intake journey templates into user-facing text.

This service encapsulates all templating concerns for the intake journey,
keeping ``IntakeJourney`` focused on schema and routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney, JourneyField
    from brief_scout.domain.ports.application_ports import TemplateRenderer


class JourneyRenderer:
    """Renders questions, acknowledgements, and extraction schema."""

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        """Initialize with a template renderer.

        Args:
            renderer: Template renderer. If omitted, a Jinja2 renderer is used.
        """
        from brief_scout.application.services.template_renderer import (
            Jinja2TemplateRenderer,
        )

        self._renderer = renderer or Jinja2TemplateRenderer()

    def render_question(
        self,
        journey: IntakeJourney,
        field: JourneyField,
        intake_data: IntakeData,
        newly_filled: list[str] | None = None,
    ) -> str:
        """Render a question for ``field`` plus context-aware acknowledgements.

        Args:
            journey: The intake journey schema.
            field: The next field to ask about.
            intake_data: Current collected intake data.
            newly_filled: Optional names of fields that were just populated in
                the latest turn. When provided, only those fields are
                acknowledged, preventing the assistant from repeating stale
                information each turn. When omitted, only the most recent
                filled field is acknowledged.
        """
        acknowledgements: list[str] = []

        if newly_filled:
            for f in journey.fields:
                if f.name == field.name:
                    continue
                if f.name not in newly_filled:
                    continue
                if f.is_empty(getattr(intake_data, f.name)):
                    continue
                ack = self.render_acknowledgement(f, intake_data)
                if ack:
                    acknowledgements.append(ack)
        else:
            # Fallback: acknowledge only the most recently collected field.
            for f in reversed(journey.fields):
                if f.name == field.name:
                    continue
                if f.is_empty(getattr(intake_data, f.name)):
                    continue
                ack = self.render_acknowledgement(f, intake_data)
                if ack:
                    acknowledgements = [ack]
                    break

        question = self._renderer.render(
            field.question_template,
            intake_data.model_dump(),
        )

        if acknowledgements:
            return f"{' '.join(acknowledgements)} {question}"
        return question

    def render_acknowledgement(self, field: JourneyField, intake_data: IntakeData) -> str:
        """Render a single field's acknowledgement template."""
        if not field.acknowledgement_template:
            return ""
        return self._renderer.render(
            field.acknowledgement_template,
            intake_data.model_dump(),
        )

    def render_researching_message(self, journey: IntakeJourney, intake_data: IntakeData) -> str:
        """Render the transition message when intake is complete."""
        return self._renderer.render(
            journey.researching_template,
            intake_data.model_dump(),
        )

    def render_extraction_schema(self, journey: IntakeJourney) -> str:
        """Render a JSON schema snippet describing all fields for LLM extraction."""
        lines: list[str] = ["{"]
        for field in journey.fields:
            if field.type == "list":
                lines.append(f'  "{field.name}": [],')
            elif field.type == "object":
                props = ", ".join(f'"{p.name}": []' for p in field.properties)
                lines.append(f'  "{field.name}": {{{props}}},')
            else:
                lines.append(f'  "{field.name}": "",')
        lines.append("}")
        return "\n".join(lines)
