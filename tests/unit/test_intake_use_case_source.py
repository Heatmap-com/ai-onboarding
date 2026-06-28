"""Unit tests for the source IntakeUseCase.

Exercises src/brief_scout/application/use_cases/intake_use_case.py.
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
from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.models import ChatSession, CreativeDirections, IntakeData
from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger
from brief_scout.infrastructure.config.journey_loader import JourneyLoader
from brief_scout.infrastructure.config.yaml_config_adapter import (
    YAMLConfigAdapter,
)
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)
from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney


@pytest.fixture
def telemetry(tmp_path: Path) -> LocalFileTelemetryAdapter:
    """Provide a telemetry adapter writing to a temp directory."""
    return LocalFileTelemetryAdapter(log_dir=str(tmp_path / "logs"))


@pytest.fixture
def config() -> YAMLConfigAdapter:
    """Provide the real YAML config adapter."""
    return YAMLConfigAdapter(config_dir="config", env="development")


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
    """Provide a source CompletenessChecker."""
    return CompletenessChecker(journey=journey, telemetry=telemetry)


@pytest.fixture
def merger(journey: IntakeJourney) -> IntakeDataMerger:
    """Provide an IntakeDataMerger."""
    return IntakeDataMerger(journey=journey)


@pytest.fixture
def use_case(
    config: YAMLConfigAdapter,
    telemetry: LocalFileTelemetryAdapter,
    storage: InMemoryStorageAdapter,
    journey: IntakeJourney,
    completeness_checker: CompletenessChecker,
    merger: IntakeDataMerger,
) -> IntakeUseCase:
    """Provide an IntakeUseCase with a mock LLM."""
    llm = AsyncMock()
    llm.provider_name = "mock"
    extractor = IntakeDataExtractor(
        llm=llm,
        journey=journey,
        provider_config_source=config,
        logger=telemetry,
    )
    acknowledgement_service = JourneyAcknowledgementService()
    differ = IntakeDataDiffer(journey=journey)

    return IntakeUseCase(
        extractor=extractor,
        acknowledgement_service=acknowledgement_service,
        differ=differ,
        storage=storage,
        completeness_checker=completeness_checker,
        merger=merger,
        logger=telemetry,
        journey=journey,
        extraction_system=config.app_config.prompts.extraction_system,
    )


class TestIntakeUseCase:
    """Tests for source IntakeUseCase."""

    @pytest.mark.asyncio
    async def test_should_process_first_message_and_ask_next_question(
        self, use_case: IntakeUseCase, storage: InMemoryStorageAdapter
    ) -> None:
        """Incomplete intake should return a follow-up question."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
        )

        session = ChatSession()
        result = await use_case.process_message(session, "We're building creative for Nike")

        assert isinstance(result, IntakeResponse)
        assert result.is_complete is False
        assert (
            "Nike" in result.assistant_message
            or "Who" in result.assistant_message
            or "Alex" in result.assistant_message
        )
        assert result.updated_session.status == "intaking"

        # Session should be persisted
        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.intake_data.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_should_transition_to_research_when_complete(
        self, use_case: IntakeUseCase
    ) -> None:
        """Complete intake should transition to researching status."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
            competitors=["Adidas", "Puma"],
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
            creative_directions=CreativeDirections(
                explore=["authentic athlete stories"],
                avoid=["generic celebrity endorsements"],
            ),
            additional_context="Focus on sustainability messaging",
        )

        session = ChatSession()
        result = await use_case.process_message(
            session, "Nike, competitors Adidas and Puma, acquisition, athletes"
        )

        assert result.is_complete is True
        assert result.updated_session.status == "researching"
        assert "research" in result.assistant_message.lower()

    @pytest.mark.asyncio
    async def test_should_merge_extracted_data_with_existing(self, use_case: IntakeUseCase) -> None:
        """Newly extracted empty fields should not overwrite existing data."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        session = ChatSession()
        session.intake_data = IntakeData(
            brand_name="Nike",
            competitors=["Adidas"],
        )
        llm.complete_structured.return_value = IntakeData(
            brand_name="Adidas",  # should be ignored
            competitors=["Puma"],  # should be appended
            primary_goal="launch",
        )

        result = await use_case.process_message(session, "launch")

        assert result.extracted_data.brand_name == "Nike"
        assert "Adidas" in result.extracted_data.competitors
        assert "Puma" in result.extracted_data.competitors
        assert result.extracted_data.primary_goal == "launch"

    @pytest.mark.asyncio
    async def test_should_preserve_existing_data_on_extraction_failure(
        self, use_case: IntakeUseCase
    ) -> None:
        """If LLM extraction fails, existing intake data should be preserved."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.side_effect = LLMCallError("boom", provider="mock")

        session = ChatSession()
        session.intake_data = IntakeData(brand_name="Nike")
        result = await use_case.process_message(session, "hello")

        assert result.extracted_data.brand_name == "Nike"
        assert result.updated_session.status == "intaking"

    @pytest.mark.asyncio
    async def test_should_generate_next_question_with_acknowledgments(
        self, use_case: IntakeUseCase
    ) -> None:
        """Next question should acknowledge known fields."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            primary_goal="acquisition",
        )

        session = ChatSession()
        result = await use_case.process_message(session, "Nike, acquisition")

        assert "Nike" in result.assistant_message
        assert "acquisition" in result.assistant_message

    def test_merge_intake_data(self, merger: IntakeDataMerger) -> None:
        """IntakeDataMerger should combine fields without overwriting."""
        existing = IntakeData(
            brand_name="Nike",
            competitors=["Adidas"],
            creative_directions=CreativeDirections(explore=["athlete stories"]),
        )
        extracted = IntakeData(
            brand_name="Puma",
            competitors=["Puma"],
            primary_goal="launch",
            creative_directions=CreativeDirections(explore=["community"]),
        )

        merged = merger.merge(existing, extracted)

        assert merged.brand_name == "Nike"
        assert merged.primary_goal == "launch"
        assert set(merged.competitors) == {"Adidas", "Puma"}
        assert set(merged.creative_directions.explore) == {"athlete stories", "community"}

    @pytest.mark.asyncio
    async def test_should_ask_optional_creative_directions_before_research(
        self, use_case: IntakeUseCase
    ) -> None:
        """When required fields are complete but creative directions are missing."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
            competitors=["Adidas", "Puma"],
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
        )

        session = ChatSession()
        result = await use_case.process_message(session, "complete nike intake")

        assert result.is_complete is False
        assert result.updated_session.status == "intaking"
        assert "creative" in result.assistant_message.lower()
        assert "creative_directions" in session.asked_optional_questions

    @pytest.mark.asyncio
    async def test_should_ask_optional_additional_context_before_research(
        self, use_case: IntakeUseCase
    ) -> None:
        """When required fields and creative directions are complete but additional context missing."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
            competitors=["Adidas", "Puma"],
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
            creative_directions=CreativeDirections(
                explore=["authentic athlete stories"],
                avoid=["generic celebrity endorsements"],
            ),
        )

        session = ChatSession()
        result = await use_case.process_message(session, "complete nike intake")

        assert result.is_complete is False
        assert result.updated_session.status == "intaking"
        assert "anything else" in result.assistant_message.lower()
        assert "additional_context" in session.asked_optional_questions

    @pytest.mark.asyncio
    async def test_should_transition_to_research_after_optional_questions_answered(
        self, use_case: IntakeUseCase
    ) -> None:
        """Once optional fields are collected, intake should transition to research."""
        llm = cast(AsyncMock, use_case._extractor._llm)
        session = ChatSession()
        session.asked_optional_questions = ["creative_directions", "additional_context"]
        llm.complete_structured.return_value = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
            competitors=["Adidas", "Puma"],
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
            creative_directions=CreativeDirections(
                explore=["authentic athlete stories"],
            ),
            additional_context="Focus on sustainability",
        )

        result = await use_case.process_message(session, "creative and context")

        assert result.is_complete is True
        assert result.updated_session.status == "researching"
        assert "research" in result.assistant_message.lower()
