"""Unit tests for the IntakeUseCase.

Per SPEC Section 6.1 — Tests conversational intake flow.
Target: 90% coverage.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest

from brief_scout.application.services import (
    IntakeDataDiffer,
    IntakeDataExtractor,
    JourneyAcknowledgementService,
)
from brief_scout.application.use_cases.intake_use_case import (
    IntakeResponse,
    IntakeUseCase,
)
from brief_scout.domain.models.intake import ChatSession, IntakeData
from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger
from brief_scout.infrastructure.config.journey_loader import JourneyLoader
from brief_scout.infrastructure.template import Jinja2TemplateRenderer
from tests.conftest import FakeLLMAdapter, InMemoryStorageAdapter, LocalFileTelemetryAdapter

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney


@pytest.fixture
def telemetry(tmp_path: Path) -> LocalFileTelemetryAdapter:
    """Provide a telemetry adapter writing to a temp directory."""
    return LocalFileTelemetryAdapter(log_dir=str(tmp_path / "logs"))


@pytest.fixture
def storage() -> InMemoryStorageAdapter:
    """Provide a fresh in-memory storage adapter."""
    return InMemoryStorageAdapter()


@pytest.fixture
def journey() -> IntakeJourney:
    """Provide the real intake journey loaded from config."""
    return JourneyLoader(config_dir="config", env="development").load()


@pytest.fixture
def completeness_checker(
    journey: IntakeJourney,
    telemetry: LocalFileTelemetryAdapter,
) -> CompletenessChecker:
    """Provide a production CompletenessChecker."""
    return CompletenessChecker(journey=journey, telemetry=telemetry)


@pytest.fixture
def merger(journey: IntakeJourney) -> IntakeDataMerger:
    """Provide an IntakeDataMerger."""
    return IntakeDataMerger(journey=journey)


@pytest.fixture
def use_case(
    fake_llm: FakeLLMAdapter,
    storage: InMemoryStorageAdapter,
    telemetry: LocalFileTelemetryAdapter,
    journey: IntakeJourney,
    completeness_checker: CompletenessChecker,
    merger: IntakeDataMerger,
) -> IntakeUseCase:
    """Provide an IntakeUseCase with test dependencies."""
    template_renderer = Jinja2TemplateRenderer()
    extractor = IntakeDataExtractor(
        llm=fake_llm,
        journey=journey,
        renderer=template_renderer,
        logger=telemetry,
    )
    acknowledgement_service = JourneyAcknowledgementService(renderer=template_renderer)
    differ = IntakeDataDiffer(journey=journey)

    extraction_system = (
        "Extract structured data from the conversation. Return ONLY valid JSON.\n\n"
        "{{schema}}\n\n"
        "Do not include markdown code fences or any explanatory text.\n"
    )

    return IntakeUseCase(
        extractor=extractor,
        acknowledgement_service=acknowledgement_service,
        differ=differ,
        storage=storage,
        completeness_checker=completeness_checker,
        merger=merger,
        logger=telemetry,
        journey=journey,
        extraction_system=extraction_system,
    )


class TestIntakeUseCase:
    """Tests for the conversational intake flow."""

    @pytest.mark.asyncio
    async def test_should_ask_first_question_for_empty_session(
        self,
        use_case: IntakeUseCase,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """Empty session → first intake question."""
        session = ChatSession()
        result = await use_case.process_message(session, "Hello!")

        assert isinstance(result, IntakeResponse)
        assert result.is_complete is False
        assert result.updated_session.session_id == session.session_id

        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert len(persisted.messages) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_should_extract_data_from_user_message(
        self,
        use_case: IntakeUseCase,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """User message with brand info → extracted brand_name."""
        fake_llm = cast(FakeLLMAdapter, use_case._extractor._llm)
        fake_llm._fixtures["extract_brand"] = {
            "_meta": {
                "match_keywords": [
                    "extract",
                    "structured",
                    "data",
                    "from this conversation",
                ],
            },
            "response": {
                "first_name": "",
                "brand_name": "Nike",
                "brand_url": "",
                "competitors": [],
                "primary_goal": "",
                "target_customer": "",
                "creative_directions": {"explore": [], "avoid": []},
                "additional_context": "",
            },
        }

        session = ChatSession()
        result = await use_case.process_message(session, "We're building creative for Nike")

        assert result.extracted_data.brand_name == "Nike"
        assert not result.is_complete  # Still missing competitors, goal, target

        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.intake_data.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_should_detect_complete_intake(
        self,
        use_case: IntakeUseCase,
    ) -> None:
        """After all required info provided → is_complete True."""
        fake_llm = cast(FakeLLMAdapter, use_case._extractor._llm)
        fake_llm._fixtures["extract_complete"] = {
            "_meta": {
                "match_keywords": [
                    "extract",
                    "structured",
                    "data",
                    "from this conversation",
                ],
            },
            "response": {
                "first_name": "Alex",
                "brand_name": "Nike",
                "brand_url": "https://nike.com",
                "competitors": ["Adidas", "Puma"],
                "primary_goal": "new customer acquisition",
                "target_customer": "18-34 year old athletes",
                "creative_directions": {
                    "explore": ["authentic athlete stories"],
                    "avoid": ["generic celebrity endorsements"],
                },
                "additional_context": "Focus on sustainability messaging",
            },
        }

        session = ChatSession()
        result = await use_case.process_message(
            session,
            "My name is Alex. We're building creative for Nike. Competitors are Adidas and Puma. "
            "We want new customer acquisition. Target is 18-34 year old athletes.",
        )

        assert result.extracted_data.first_name == "Alex"
        assert result.extracted_data.brand_name == "Nike"
        assert "Adidas" in result.extracted_data.competitors
        assert result.is_complete

    @pytest.mark.asyncio
    async def test_should_track_conversation_flow(
        self,
        use_case: IntakeUseCase,
    ) -> None:
        """Multiple messages build up conversation history."""
        fake_llm = cast(FakeLLMAdapter, use_case._extractor._llm)
        fake_llm._fixtures["extract_brand"] = {
            "_meta": {
                "match_keywords": [
                    "extract",
                    "structured",
                    "data",
                    "from this conversation",
                ],
            },
            "response": {
                "brand_name": "Nike",
                "competitors": [],
                "primary_goal": "",
                "target_customer": "",
                "creative_directions": {"explore": [], "avoid": []},
            },
        }
        fake_llm._fixtures["extract_competitors"] = {
            "_meta": {
                "match_keywords": [
                    "extract",
                    "structured",
                    "data",
                    "from this conversation",
                ],
            },
            "response": {
                "brand_name": "Nike",
                "competitors": ["Adidas", "Puma"],
                "primary_goal": "",
                "target_customer": "",
                "creative_directions": {"explore": [], "avoid": []},
            },
        }

        session = ChatSession()
        await use_case.process_message(session, "We're building creative for Nike")
        assert len(session.messages) == 2  # user + assistant

        await use_case.process_message(session, "Competitors are Adidas and Puma")
        assert len(session.messages) == 4  # + user + assistant

    @pytest.mark.asyncio
    async def test_should_return_assistant_message(
        self,
        use_case: IntakeUseCase,
    ) -> None:
        """Result should always contain a non-empty assistant_message."""
        session = ChatSession()
        result = await use_case.process_message(session, "Hi")
        assert result.assistant_message
        assert isinstance(result.assistant_message, str)


class TestIntakeUseCaseWithMockLLM:
    """Focused unit tests using a mocked LLM for deterministic assertions."""

    @pytest.fixture
    def mock_use_case(
        self,
        storage: InMemoryStorageAdapter,
        telemetry: LocalFileTelemetryAdapter,
        journey: IntakeJourney,
        completeness_checker: CompletenessChecker,
        merger: IntakeDataMerger,
    ) -> IntakeUseCase:
        """Provide an IntakeUseCase with a mock LLM."""
        llm = AsyncMock()
        llm.provider_name = "mock"
        template_renderer = Jinja2TemplateRenderer()
        extractor = IntakeDataExtractor(
            llm=llm,
            journey=journey,
            renderer=template_renderer,
            logger=telemetry,
        )
        acknowledgement_service = JourneyAcknowledgementService(renderer=template_renderer)
        differ = IntakeDataDiffer(journey=journey)

        extraction_system = "Extract structured data.\n\n{{schema}}"

        return IntakeUseCase(
            extractor=extractor,
            acknowledgement_service=acknowledgement_service,
            differ=differ,
            storage=storage,
            completeness_checker=completeness_checker,
            merger=merger,
            logger=telemetry,
            journey=journey,
            extraction_system=extraction_system,
        )

    @pytest.mark.asyncio
    async def test_should_persist_session(
        self,
        mock_use_case: IntakeUseCase,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """After processing, session should be persisted to storage."""
        llm = cast(AsyncMock, mock_use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(brand_name="Nike")

        session = ChatSession()
        await mock_use_case.process_message(session, "We're building creative for Nike")

        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.session_id == session.session_id
        assert len(persisted.messages) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_should_transition_status_on_complete(
        self,
        mock_use_case: IntakeUseCase,
    ) -> None:
        """When intake becomes complete, session status should change."""
        llm = cast(AsyncMock, mock_use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas", "Puma"],
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
            creative_directions={
                "explore": ["authentic athlete stories"],
                "avoid": ["generic celebrity endorsements"],
            },
            additional_context="Focus on sustainability messaging",
        )

        session = ChatSession()
        result = await mock_use_case.process_message(
            session,
            "We're building creative for Nike. Competitors are Adidas and Puma. "
            "We want new customer acquisition. Target is 18-34 athletes.",
        )

        assert result.is_complete
        assert result.updated_session.status == "intaking"
