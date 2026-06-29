"""Journey acknowledgement service — renders the next question with context-aware acks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.application.services.journey_renderer import JourneyRenderer
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney, JourneyField
    from brief_scout.domain.ports.application_ports import TemplateRenderer


class JourneyAcknowledgementService:
    """Renders the next intake question, acknowledging what the user just said.

    This service is intentionally thin: it delegates template rendering to
    ``JourneyRenderer`` while owning the policy of *which* fields to
    acknowledge (only those newly provided in the latest turn).
    """

    def __init__(self, renderer: TemplateRenderer) -> None:
        """Initialize the service with a template renderer."""
        self._renderer = renderer
        self._journey_renderer: JourneyRenderer | None = None

    def _get_journey_renderer(self) -> JourneyRenderer:
        """Lazy-load the journey renderer."""
        if self._journey_renderer is None:
            from brief_scout.application.services.journey_renderer import (
                JourneyRenderer,
            )

            self._journey_renderer = JourneyRenderer(renderer=self._renderer)
        return self._journey_renderer

    def render_next_question(
        self,
        journey: IntakeJourney,
        next_field: JourneyField,
        intake_data: IntakeData,
        newly_filled: list[str] | None = None,
    ) -> str:
        """Render the question for ``next_field`` plus acknowledgements.

        Args:
            journey: The intake journey schema.
            next_field: The next field to ask about.
            intake_data: Current collected intake data.
            newly_filled: Names of fields populated in the latest user turn.

        Returns:
            The assistant message to display.
        """
        return self._get_journey_renderer().render_question(
            journey,
            next_field,
            intake_data,
            newly_filled=newly_filled,
        )

    def render_researching_message(
        self,
        journey: IntakeJourney,
        intake_data: IntakeData,
    ) -> str:
        """Render the transition message when intake is complete."""
        return self._get_journey_renderer().render_researching_message(
            journey,
            intake_data,
        )
