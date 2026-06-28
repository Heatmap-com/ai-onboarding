"""Intake use case — orchestrates the conversational brief intake flow.

Per SPEC 6.1 — Processes user messages, extracts structured data, checks
completeness, and transitions to research when enough data is collected.

The interview flow is now driven by the declarative ``IntakeJourney`` schema,
so adding or reordering fields should not require changes to this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Template
from pydantic import BaseModel, Field

from brief_scout.domain.errors import BriefScoutError, LLMCallError
from brief_scout.domain.models import ChatMessage, ChatSession, IntakeData
from brief_scout.domain.ports import Prompt, TelemetryEvent

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports import (
        BriefStoragePort,
        ConfigurationPort,
        LLMPort,
        TelemetryPort,
    )
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
    - Process user messages and generate assistant responses.
    - Extract structured data from conversation via LLM.
    - Track intake completeness via CompletenessChecker.
    - Transition to research phase when data is complete.

    Dependencies (constructor-injected):
        llm: LLM adapter for completions and structured extraction.
        config: Configuration source for prompt templates.
        telemetry: Telemetry adapter for logging and events.
        storage: Storage adapter for session persistence.
        journey: Declarative intake journey schema.
        completeness_checker: Service evaluating intake completeness.
        merger: Service merging extracted data into existing data.
    """

    def __init__(
        self,
        llm: LLMPort,
        config: ConfigurationPort,
        telemetry: TelemetryPort,
        storage: BriefStoragePort,
        journey: IntakeJourney,
        completeness_checker: CompletenessChecker,
        merger: IntakeDataMerger,
    ) -> None:
        """Initialize the intake use case with all dependencies."""
        self._llm = llm
        self._config = config
        self._telemetry = telemetry
        self._storage = storage
        self._journey = journey
        self._completeness_checker = completeness_checker
        self._merger = merger

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
    ) -> IntakeResponse:
        """Process a user message and return assistant response + updated session.

        Steps:
            1. Append user message to session.
            2. Extract structured IntakeData from conversation via LLM.
            3. Merge extracted data with existing data.
            4. Determine the next field to ask about (if any).
            5. Generate assistant response and persist session.
            6. Return IntakeResponse.

        Args:
            session: The current chat session.
            user_message: Raw text message from the user.

        Returns:
            IntakeResponse with assistant message and completion state.
        """
        self._telemetry.log(
            "Processing intake message",
            level="INFO",
            session_id=session.session_id,
            message_preview=user_message[:100],
        )

        # Step 1: Add user message to session
        session.messages.append(
            ChatMessage(role="user", content=user_message),
        )

        # Step 2: Extract structured data from conversation
        try:
            extracted = await self._extract_structured_data(session.messages)
        except BriefScoutError:
            # If extraction fails, keep existing data and continue
            extracted = session.intake_data
            self._telemetry.log(
                "Structured data extraction failed; preserving existing data",
                level="WARNING",
                session_id=session.session_id,
            )

        # Step 3: Merge extracted data with existing
        merged = self._merger.merge(session.intake_data, extracted)
        session.intake_data = merged

        # Step 4: Check completeness for telemetry
        completeness_result = self._completeness_checker.check(merged)
        session.status = "intaking"

        # Step 5: Determine next action
        next_field = self._journey.next_field(
            merged,
            session.asked_optional_questions,
        )

        if next_field is not None:
            assistant_message = self._journey.render_question(next_field, merged)
            if not next_field.required and next_field.name not in session.asked_optional_questions:
                session.asked_optional_questions.append(next_field.name)
            is_complete = False
        else:
            assistant_message = self._journey.render_researching_message(merged)
            session.status = "researching"
            is_complete = True

        session.messages.append(
            ChatMessage(role="assistant", content=assistant_message),
        )

        # Step 6: Save session
        await self._storage.save_session(session)

        self._telemetry.record_event(
            TelemetryEvent(
                event_type="intake.message.processed",
                correlation_id=self._telemetry.get_correlation_id(),
                data={
                    "session_id": session.session_id,
                    "is_complete": is_complete,
                    "completion_confidence": completeness_result.confidence,
                    "missing_fields": completeness_result.missing_fields,
                },
            ),
        )

        return IntakeResponse(
            assistant_message=assistant_message,
            updated_session=session,
            is_complete=is_complete,
            extracted_data=merged,
        )

    async def _extract_structured_data(
        self,
        messages: list[ChatMessage],
    ) -> IntakeData:
        """Extract IntakeData from conversation history using LLM.

        Builds an extraction prompt from the conversation, calls the LLM with
        structured output constraints, and returns the parsed IntakeData.

        Args:
            messages: Full conversation history.

        Returns:
            Extracted IntakeData from the conversation.

        Raises:
            LLMCallError: If the LLM call or parsing fails.
        """
        self._telemetry.log(
            "Extracting structured data from conversation",
            level="DEBUG",
        )

        # Build conversation transcript
        transcript_lines: list[str] = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            transcript_lines.append(f"{prefix}: {msg.content}")
        transcript = "\n".join(transcript_lines)

        # Build extraction prompt, injecting the auto-generated schema
        prompts_config = self._config.app_config.prompts
        system_template = Template(prompts_config.extraction_system)
        system_prompt = system_template.render(
            schema=self._journey.render_extraction_schema(),
        )
        prompt = Prompt(
            system=system_prompt,
            user=f"Extract structured data from this conversation:\n\n{transcript}",
        )

        span_id = self._telemetry.start_span(
            "intake.extract_structured_data",
        )

        try:
            extraction_config = self._select_extraction_config(messages)
            result = await self._llm.complete_structured(
                prompt,
                IntakeData,
                config=extraction_config,
            )
            self._telemetry.log(
                "Structured data extraction successful",
                level="DEBUG",
                brand_name=result.brand_name,
                competitors_count=len(result.competitors),
            )
            return result
        except Exception as exc:
            self._telemetry.log(
                f"Structured extraction failed: {exc}",
                level="ERROR",
            )
            raise LLMCallError(
                message=f"Failed to extract structured intake data: {exc}",
                provider=self._llm.provider_name,
            ) from exc
        finally:
            self._telemetry.end_span(span_id)

    def _select_extraction_config(
        self,
        messages: list[ChatMessage],
    ) -> dict[str, object] | None:
        """Select extraction config for the FakeLLM adapter.

        The FakeLLM adapter uses ``demo_turn`` to return cumulative demo data
        from ``demo_journey.yaml``. Real LLM adapters ignore the config and
        perform live extraction.

        Args:
            messages: Conversation history.

        Returns:
            Config dict with ``demo_turn``, or ``None`` for free matching.
        """
        user_turns = sum(1 for msg in messages if msg.role == "user")
        return {"demo_turn": user_turns}
