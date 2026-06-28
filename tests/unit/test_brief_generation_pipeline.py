"""Unit tests for BriefGenerationPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from brief_scout.application.services.brief_generation_pipeline import (
    BriefGenerationPipeline,
    PipelineEvent,
    _map_research_status,
)
from brief_scout.application.services.research_pipeline import (
    PipelineEvent as ResearchPipelineEvent,
)
from brief_scout.application.services.research_pipeline import (
    ResearchPipeline,
)
from brief_scout.application.use_cases.intake_use_case import IntakeResponse
from brief_scout.domain.models import (
    BrandAuditResult,
    Brief,
    ChatSession,
    IntakeData,
    ResearchBundle,
)
from brief_scout.domain.models.intake import Status
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)


class FakeIntakeUseCase:
    """Intake use-case stub that returns a deterministic response."""

    def __init__(self, is_complete: bool = True) -> None:
        self._is_complete = is_complete

    async def process_message(
        self,
        session: ChatSession,
        _user_message: str,
    ) -> IntakeResponse:
        session.intake_data = IntakeData(brand_name="Nike")
        if self._is_complete:
            session.status = Status.RESEARCHING
        return IntakeResponse(
            assistant_message="Got it.",
            updated_session=session,
            is_complete=self._is_complete,
            extracted_data=session.intake_data,
        )


class FakeSynthesisUseCase:
    """Synthesis use-case stub that returns a deterministic brief."""

    async def execute(
        self,
        _intake_data: IntakeData,
        _research_bundle: ResearchBundle,
    ) -> Brief:
        return Brief(brand_name="Nike")


class FakeResearchStep:
    """Simple research step that returns an empty brand audit."""

    name = "brand_audit"

    async def execute(self, _intake_data: IntakeData) -> BrandAuditResult:
        return BrandAuditResult(brand_positioning="Nike")


@pytest.fixture
def storage() -> InMemoryStorageAdapter:
    """Provide a fresh in-memory storage adapter."""
    return InMemoryStorageAdapter()


class TestBriefGenerationPipeline:
    """Tests for the end-to-end brief generation pipeline."""

    @pytest.mark.asyncio
    async def test_run_complete_flow(self, storage: InMemoryStorageAdapter) -> None:
        """A complete intake should yield intake, research, synthesis, and complete events."""
        research = ResearchPipeline(steps=[FakeResearchStep()])
        pipeline = BriefGenerationPipeline(
            intake_use_case=FakeIntakeUseCase(is_complete=True),
            research_pipeline=research,
            synthesis_use_case=FakeSynthesisUseCase(),
            storage=storage,
        )
        session = ChatSession()
        events = [event async for event in pipeline.run(session, "We're Nike")]

        stages = [e.stage for e in events]
        assert "intake" in stages
        assert "research" in stages
        assert "synthesis" in stages
        assert "complete" in stages
        assert session.status == Status.COMPLETE

        brief = await storage.get_brief(session.session_id)
        assert brief is not None
        assert brief.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_run_stops_when_intake_incomplete(self, storage: InMemoryStorageAdapter) -> None:
        """An incomplete intake should yield only the intake event."""
        research = ResearchPipeline(steps=[FakeResearchStep()])
        pipeline = BriefGenerationPipeline(
            intake_use_case=FakeIntakeUseCase(is_complete=False),
            research_pipeline=research,
            synthesis_use_case=FakeSynthesisUseCase(),
            storage=storage,
        )
        session = ChatSession()
        events = [event async for event in pipeline.run(session, "Hi")]

        assert len(events) == 1
        assert events[0].stage == "intake"
        assert events[0].payload["is_complete"] is False
        assert session.status != Status.COMPLETE

    @pytest.mark.asyncio
    async def test_run_reports_failure(self, storage: InMemoryStorageAdapter) -> None:
        """An exception should yield a failed complete event."""
        failing_intake = AsyncMock()
        failing_intake.process_message.side_effect = RuntimeError("intake exploded")
        research = ResearchPipeline(steps=[FakeResearchStep()])
        pipeline = BriefGenerationPipeline(
            intake_use_case=failing_intake,
            research_pipeline=research,
            synthesis_use_case=FakeSynthesisUseCase(),
            storage=storage,
        )
        session = ChatSession()
        events = [event async for event in pipeline.run(session, "Hi")]

        assert events[-1].stage == "complete"
        assert events[-1].status == "failed"
        assert "intake exploded" in events[-1].payload["error"]


class TestMapResearchStatus:
    """Tests for research-to-brief status mapping."""

    def test_maps_known_statuses(self) -> None:
        """Known statuses should map to themselves."""
        assert _map_research_status("started") == "started"
        assert _map_research_status("complete") == "complete"
        assert _map_research_status("failed") == "failed"

    def test_maps_unknown_to_progress(self) -> None:
        """Unknown statuses should map to progress."""
        assert _map_research_status("running") == "progress"


class TestPipelineEventModel:
    """Tests for PipelineEvent default values."""

    def test_defaults(self) -> None:
        """Defaults should match expected values."""
        event = PipelineEvent()
        assert event.stage == "intake"
        assert event.status == "progress"
        assert event.payload == {}


class TestResearchPipelineEvent:
    """Tests for research pipeline event defaults."""

    def test_defaults(self) -> None:
        """Defaults should be empty."""
        event = ResearchPipelineEvent()
        assert event.stage == ""
        assert event.status == ""
        assert event.payload == {}
