"""Intake use case — orchestrates the conversational brief intake flow.

Per SPEC 6.1 — Processes user messages, extracts structured data, checks
completeness, and transitions to research when enough data is collected.

The interview flow is driven by the declarative ``IntakeJourney`` schema,
so adding or reordering fields should not require changes to this file.

This module is intentionally thin. The heavy lifting lives in:
  - ``IntakeDataExtractor`` — LLM prompt building, extraction, parsing.
  - ``JourneyAcknowledgementService`` — rendering the next question.
  - ``IntakeDataDiffer`` — detecting newly populated fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from brief_scout.domain.errors import BriefScoutError
from brief_scout.domain.models import ChatMessage, ChatSession, IntakeData
from brief_scout.domain.models.intake import Status

if TYPE_CHECKING:
    from brief_scout.application.services.intake_data_differ import (
        IntakeDataDiffer,
    )
    from brief_scout.application.services.intake_data_extractor import (
        IntakeDataExtractor,
    )
    from brief_scout.application.services.journey_acknowledgement_service import (
        JourneyAcknowledgementService,
    )
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.application_ports import LoggerPort, SessionWriter
    from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger


class IntakeResponse(BaseModel):
    """Response from processing an intake message.

    Attributes:
        assistant_message: The chat response to display to the user.
        updated_session: The updated chat session state.
        is_complete: Whether intake data is complete and ready for research.
        extracted_data: The structured data extracted from the conversation.
    """

    assistant_message: str = ""
    updated_session: ChatSession = Field(default_factory=ChatSession)
    is_complete: bool = False
    extracted_data: IntakeData = Field(default_factory=IntakeData)


class IntakeUseCase:
    """Orchestrates the conversational intake flow.

    Responsibilities:
    - Append the user message to the session.
    - Delegate structured data extraction to ``IntakeDataExtractor``.
    - Merge extracted data with existing data.
    - Determine the next field to ask about (if any).
    - Render the assistant response via ``JourneyAcknowledgementService``.
    - Persist the session via ``SessionWriter``.

    Dependencies (constructor-injected):
        extractor: Extracts IntakeData from conversation history.
        acknowledgement_service: Renders questions and acknowledgements.
        differ: Detects fields newly populated this turn.
        storage: Narrow port for persisting chat sessions.
        completeness_checker: Evaluates intake completeness.
        merger: Merges extracted data into existing data.
        logger: Logger port for telemetry.
        journey: Declarative intake journey schema (routing).
        extraction_system: System prompt used for LLM extraction.
    """

    def __init__(
        self,
        extractor: IntakeDataExtractor,
        acknowledgement_service: JourneyAcknowledgementService,
        differ: IntakeDataDiffer,
        storage: SessionWriter,
        completeness_checker: CompletenessChecker,
        merger: IntakeDataMerger,
        logger: LoggerPort,
        journey: IntakeJourney,
        extraction_system: str,
    ) -> None:
        """Initialize the intake use case with all collaborators."""
        self._extractor = extractor
        self._acknowledgement_service = acknowledgement_service
        self._differ = differ
        self._storage = storage
        self._completeness_checker = completeness_checker
        self._merger = merger
        self._logger = logger
        self._journey = journey
        self._extraction_system = extraction_system

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
    ) -> IntakeResponse:
        """Process a user message and return assistant response + updated session.

        Args:
            session: The current chat session.
            user_message: Raw text message from the user.

        Returns:
            IntakeResponse with assistant message and completion state.
        """
        self._logger.log(
            "Processing intake message",
            level="INFO",
            session_id=session.session_id,
            message_preview=user_message[:100],
        )

        # Step 1: Add user message to session
        session.messages.append(
            ChatMessage(role="user", content=user_message),
        )

        # Snapshot current data so we can tell what was newly provided this turn.
        previous_intake = session.intake_data.model_copy(deep=True)

        # Step 2: Extract structured data from conversation
        try:
            extracted = await self._extractor.extract(
                session.messages,
                self._extraction_system,
            )
        except BriefScoutError:
            # If extraction fails, keep existing data and continue
            extracted = session.intake_data
            self._logger.log(
                "Structured data extraction failed; preserving existing data",
                level="WARNING",
                session_id=session.session_id,
            )

        # Step 3: Merge extracted data with existing
        merged = self._merger.merge(session.intake_data, extracted)
        session.intake_data = merged

        # Identify fields that went from empty to populated this turn. The
        # renderer uses this to acknowledge only what the user just said
        # instead of restating the brand on every turn.
        newly_filled = self._differ.newly_filled_fields(previous_intake, merged)

        # Step 4: Check completeness for telemetry
        completeness_result = self._completeness_checker.check(merged)
        session.status = Status.INTAKING

        # Step 5: Determine next action
        next_field = self._journey.next_field(
            merged,
            session.asked_optional_questions,
        )

        if next_field is not None:
            assistant_message = self._acknowledgement_service.render_next_question(
                self._journey,
                next_field,
                merged,
                newly_filled=newly_filled,
            )
            if not next_field.required and next_field.name not in session.asked_optional_questions:
                session.asked_optional_questions.append(next_field.name)
            is_complete = False
        else:
            assistant_message = self._acknowledgement_service.render_researching_message(
                self._journey,
                merged,
            )
            session.status = Status.RESEARCHING
            is_complete = True

        session.messages.append(
            ChatMessage(role="assistant", content=assistant_message),
        )

        # Step 6: Save session
        await self._storage.save_session(session)

        self._logger.log(
            "Intake message processed",
            level="INFO",
            session_id=session.session_id,
            is_complete=is_complete,
            missing_fields=completeness_result.missing_fields,
            confidence=completeness_result.confidence,
        )

        return IntakeResponse(
            assistant_message=assistant_message,
            updated_session=session,
            is_complete=is_complete,
            extracted_data=merged,
        )
