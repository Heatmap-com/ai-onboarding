"""Completeness checker — evaluates intake data sufficiency.

Uses the declarative intake journey to decide whether enough information has
been collected to trigger the research phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class CompletenessResult(BaseModel):
    """Result of evaluating intake data completeness.

    Attributes:
        is_complete: True if all required fields are populated.
        missing_fields: List of required field names that are empty.
        ready_to_research: Alias for is_complete — signals research can begin.
        confidence: 0.0 to 1.0 score indicating completeness fraction.
    """

    is_complete: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    ready_to_research: bool = False
    confidence: float = 0.0


class CompletenessChecker:
    """Evaluates whether collected intake data is sufficient to trigger research.

    The checker inspects the required fields defined by the intake journey and
    produces a detailed result including which fields (if any) are still missing.
    """

    def __init__(
        self,
        journey: IntakeJourney,
        telemetry: TelemetryPort,
    ) -> None:
        """Initialize the checker with a journey schema and telemetry port.

        Args:
            journey: The intake journey defining required fields.
            telemetry: Telemetry port for logging completeness checks.
        """
        self._journey = journey
        self._telemetry = telemetry

    def check(self, intake_data: IntakeData) -> CompletenessResult:
        """Evaluate intake data completeness.

        Args:
            intake_data: The structured intake data to evaluate.

        Returns:
            A CompletenessResult with detailed status information.
        """
        missing_fields: list[str] = []

        for field in self._journey.required_fields:
            value = getattr(intake_data, field.name)
            if field.is_empty(value):
                missing_fields.append(field.name)

        is_complete = len(missing_fields) == 0
        confidence = intake_data.completion_score

        result = CompletenessResult(
            is_complete=is_complete,
            missing_fields=missing_fields,
            ready_to_research=is_complete,
            confidence=confidence,
        )

        self._telemetry.log(
            message="Intake completeness check completed",
            level="INFO",
            is_complete=is_complete,
            missing_fields=missing_fields,
            confidence=confidence,
        )

        return result
