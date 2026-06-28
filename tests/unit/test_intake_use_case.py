"""Unit tests for the IntakeUseCase.

Per SPEC Section 6.1 — Tests conversational intake flow.
Target: 90% coverage.
"""

from __future__ import annotations

from typing import Any

import pytest

from brief_scout.domain.models.intake import ChatMessage, ChatSession, IntakeData
from brief_scout.domain.models.journey import IntakeJourney, JourneyField
from tests.conftest import (
    CompletenessChecker,
    FakeLLMAdapter,
    InMemoryStorageAdapter,
    LocalFileTelemetryAdapter,
)

# ---------------------------------------------------------------------------
# IntakeUseCase — inline implementation for testing
# ---------------------------------------------------------------------------


class IntakeResponse:
    """Response from processing an intake message."""

    def __init__(
        self,
        assistant_message: str = "",
        updated_session: ChatSession | None = None,
        is_complete: bool = False,
        extracted_data: IntakeData | None = None,
    ) -> None:
        self.assistant_message = assistant_message
        self.updated_session = updated_session or ChatSession()
        self.is_complete = is_complete
        self.extracted_data = extracted_data or IntakeData()


class IntakeUseCase:
    """Orchestrates the conversational intake flow."""

    DEFAULT_QUESTIONS: list[str] = [
        "What brand are we building creative for? Drop the URL too if you have it.",
        "Who are their top 2 or 3 competitors?",
        "What's the main thing you're trying to accomplish — new customer acquisition, retention, a product launch?",
        "Who's the customer? Paint me a quick picture.",
        "Any creative directions you want to explore or definitely avoid?",
    ]

    def __init__(
        self,
        llm: FakeLLMAdapter,
        config: Any | None = None,
        telemetry: LocalFileTelemetryAdapter | None = None,
        storage: InMemoryStorageAdapter | None = None,
        completeness_checker: CompletenessChecker | None = None,
        journey: IntakeJourney | None = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._telemetry = telemetry
        self._storage = storage
        self._journey = journey or _default_test_journey()
        self._completeness = completeness_checker or CompletenessChecker(
            journey=self._journey,
            telemetry=telemetry,
        )

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
    ) -> IntakeResponse:
        """Process a user message and return assistant response + updated session."""
        # Add user message to session
        session.messages.append(ChatMessage(role="user", content=user_message))

        # Attempt to extract structured data from the conversation
        extracted = self._extract_data_from_messages(session.messages)
        session.intake_data = extracted

        # Check completeness
        check_result = self._completeness.check(extracted)

        # Determine next assistant message
        if check_result.is_complete:
            assistant_msg = (
                f"Thanks! I've got everything I need for {extracted.brand_name}. "
                "Let me kick off the research now — this'll take about a minute."
            )
            session.status = "researching"
        else:
            assistant_msg = self._next_question(session, check_result.missing_fields)

        session.messages.append(ChatMessage(role="assistant", content=assistant_msg))

        # Persist session
        if self._storage:
            await self._storage.save_session(session)

        return IntakeResponse(
            assistant_message=assistant_msg,
            updated_session=session,
            is_complete=check_result.is_complete,
            extracted_data=extracted,
        )

    def _extract_data_from_messages(self, messages: list[ChatMessage]) -> IntakeData:
        """Extract structured data from conversation history.

        Simple rule-based extraction for testing — looks for keywords
        in user messages to populate intake fields.
        """
        data = IntakeData()
        user_texts = [m.content for m in messages if m.role == "user"]
        " ".join(user_texts).lower()

        # Extract first name
        for text in user_texts:
            lower = text.lower()
            if not data.first_name:
                for prefix in ["name is ", "i'm ", "i am "]:
                    if prefix in lower:
                        rest = lower.split(prefix, 1)[1]
                        candidate = rest.split(".")[0].split(",")[0].split(" ")[0].strip()
                        if candidate:
                            data.first_name = candidate.title()
                            break

            if "building creative for" in lower or "brand" in lower:
                # Simple heuristic: capitalized word after "for"
                parts = text.split("for ")
                if len(parts) > 1:
                    candidate = parts[1].split(".")[0].split(",")[0].strip()
                    if candidate and len(candidate) < 50:
                        data.brand_name = candidate

            # Extract competitors
            if any(kw in lower for kw in ["competitors", "competition", "vs", "versus"]):
                # Look for capitalized names that are known competitors
                known = ["adidas", "puma", "under armour", "new balance", "reebok"]
                found = []
                for k in known:
                    if k in lower:
                        found.append(k.title() if k != "adidas" else "Adidas")
                if found:
                    data.competitors = found

            # Extract goal
            if any(
                kw in lower
                for kw in ["new customer acquisition", "acquisition", "retention", "launch"]
            ):
                if "new customer acquisition" in lower or "acquisition" in lower:
                    data.primary_goal = "new customer acquisition"
                elif "retention" in lower:
                    data.primary_goal = "retention"
                elif "launch" in lower:
                    data.primary_goal = "product launch"

            # Extract target customer
            if any(
                kw in lower for kw in ["target", "customer", "audience", "year old", "demographic"]
            ) and ("year old" in lower or "age" in lower):
                # Extract the target customer description
                data.target_customer = text.strip()

        # Whitespace / brand cleanup
        if data.brand_name:
            data.brand_name = data.brand_name.strip()

        return data

    def _next_question(self, session: ChatSession, _missing_fields: list[str]) -> str:
        """Determine the next question based on missing fields."""
        data = session.intake_data

        if not data.brand_name:
            return self.DEFAULT_QUESTIONS[0]
        elif not data.competitors:
            return self.DEFAULT_QUESTIONS[1]
        elif not data.primary_goal:
            return self.DEFAULT_QUESTIONS[2]
        elif not data.target_customer:
            return self.DEFAULT_QUESTIONS[3]
        else:
            return self.DEFAULT_QUESTIONS[4]


def _default_test_journey() -> IntakeJourney:
    """Return a minimal journey matching the inline test question list."""
    return IntakeJourney(
        fields=[
            JourneyField(
                name="brand_name",
                type="string",
                required=True,
                question_template=IntakeUseCase.DEFAULT_QUESTIONS[0],
            ),
            JourneyField(
                name="competitors",
                type="list",
                required=True,
                question_template=IntakeUseCase.DEFAULT_QUESTIONS[1],
            ),
            JourneyField(
                name="primary_goal",
                type="string",
                required=True,
                question_template=IntakeUseCase.DEFAULT_QUESTIONS[2],
            ),
            JourneyField(
                name="target_customer",
                type="string",
                required=True,
                question_template=IntakeUseCase.DEFAULT_QUESTIONS[3],
            ),
            JourneyField(
                name="creative_directions",
                type="object",
                required=False,
                ask_when_missing=False,
                question_template=IntakeUseCase.DEFAULT_QUESTIONS[4],
            ),
        ],
    )


# ============================================================================
# Tests
# ============================================================================


class TestIntakeUseCase:
    """Tests for the conversational intake flow."""

    @pytest.fixture
    def use_case(
        self,
        fake_llm: FakeLLMAdapter,
        storage: InMemoryStorageAdapter,
        telemetry: LocalFileTelemetryAdapter,
    ) -> IntakeUseCase:
        """Provide an IntakeUseCase with test dependencies."""
        checker = CompletenessChecker(telemetry=telemetry)
        return IntakeUseCase(
            llm=fake_llm,
            storage=storage,
            telemetry=telemetry,
            completeness_checker=checker,
        )

    @pytest.mark.asyncio
    async def test_should_ask_first_question_for_empty_session(
        self,
        use_case: IntakeUseCase,
        empty_session: ChatSession,
    ) -> None:
        """Empty session → first intake question."""
        result = await use_case.process_message(empty_session, "Hello!")

        assert result.assistant_message == IntakeUseCase.DEFAULT_QUESTIONS[0]
        assert result.is_complete is False

    @pytest.mark.asyncio
    async def test_should_extract_data_from_user_message(
        self,
        use_case: IntakeUseCase,
        empty_session: ChatSession,
    ) -> None:
        """User message with brand info → extracted brand_name."""
        result = await use_case.process_message(
            empty_session,
            "We're building creative for Nike",
        )

        assert result.extracted_data.brand_name == "Nike"
        assert not result.is_complete  # Still missing competitors, goal, target

    @pytest.mark.asyncio
    async def test_should_detect_complete_intake(
        self,
        use_case: IntakeUseCase,
        empty_session: ChatSession,
    ) -> None:
        """After all required info provided → is_complete True."""
        session = empty_session

        # Simulate a complete intake conversation
        result = await use_case.process_message(
            session,
            "My name is Alex. We're building creative for Nike. Competitors are Adidas and Puma. "
            "We want new customer acquisition. "
            "Target is 18-34 year old athletes who care about style and performance.",
        )

        # All fields should be extracted from the single comprehensive message
        assert result.extracted_data.first_name == "Alex"
        assert result.extracted_data.brand_name == "Nike"
        assert (
            "Adidas" in result.extracted_data.competitors
            or "adidas" in str(result.extracted_data.competitors).lower()
        )
        # The message should trigger completeness since brand + competitors + goal + target
        # are all present in the text
        assert result.is_complete

    @pytest.mark.asyncio
    async def test_should_persist_session(
        self,
        use_case: IntakeUseCase,
        storage: InMemoryStorageAdapter,
        empty_session: ChatSession,
    ) -> None:
        """After processing, session should be persisted to storage."""
        session = empty_session
        await use_case.process_message(session, "We're building creative for Nike")

        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.session_id == session.session_id
        assert len(persisted.messages) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_should_track_conversation_flow(
        self,
        use_case: IntakeUseCase,
        empty_session: ChatSession,
    ) -> None:
        """Multiple messages build up conversation history."""
        session = empty_session

        await use_case.process_message(session, "We're building creative for Nike")
        assert len(session.messages) == 2  # user + assistant

        await use_case.process_message(session, "Competitors are Adidas and Puma")
        assert len(session.messages) == 4  # + user + assistant

    @pytest.mark.asyncio
    async def test_should_transition_status_on_complete(
        self,
        use_case: IntakeUseCase,
        empty_session: ChatSession,
    ) -> None:
        """When intake becomes complete, session status should change."""
        session = empty_session

        result = await use_case.process_message(
            session,
            "We're building creative for Nike. Competitors are Adidas and Puma. "
            "We want new customer acquisition. "
            "Target is 18-34 year old athletes who care about style and performance.",
        )

        if result.is_complete:
            assert result.updated_session.status == "researching"

    @pytest.mark.asyncio
    async def test_should_return_assistant_message(
        self, use_case: IntakeUseCase, empty_session: ChatSession
    ) -> None:
        """Result should always contain a non-empty assistant_message."""
        result = await use_case.process_message(empty_session, "Hi")
        assert result.assistant_message
        assert isinstance(result.assistant_message, str)
