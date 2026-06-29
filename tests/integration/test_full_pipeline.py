"""End-to-end integration tests for the Brief Scout pipeline.

Per SPEC Section 13.2 — Validates full flow: intake → research → synthesis → brief.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from brief_scout.application.services import (
    DefaultResearchStepRegistry,
    IntakeDataDiffer,
    IntakeDataExtractor,
    JourneyAcknowledgementService,
)
from brief_scout.application.services.brief_generation_pipeline import (
    BriefGenerationPipeline,
)
from brief_scout.application.services.brief_markdown_renderer import BriefMarkdownRenderer
from brief_scout.application.services.research_pipeline import ResearchPipeline
from brief_scout.application.use_cases import IntakeUseCase, SynthesisUseCase
from brief_scout.domain.models.brief import Brief
from brief_scout.domain.models.intake import ChatSession
from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger
from brief_scout.infrastructure.config.journey_loader import JourneyLoader
from brief_scout.infrastructure.config.yaml_config_adapter import YAMLConfigAdapter
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
def config() -> YAMLConfigAdapter:
    """Provide the real YAML config adapter."""
    return YAMLConfigAdapter(config_dir="config", env="development")


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
def pipeline(
    fake_llm: FakeLLMAdapter,
    storage: InMemoryStorageAdapter,
    telemetry: LocalFileTelemetryAdapter,
    config: YAMLConfigAdapter,
    journey: IntakeJourney,
    completeness_checker: CompletenessChecker,
    merger: IntakeDataMerger,
) -> BriefGenerationPipeline:
    """Wire the production BriefGenerationPipeline with test adapters."""
    template_renderer = Jinja2TemplateRenderer()

    extractor = IntakeDataExtractor(
        llm=fake_llm,
        journey=journey,
        renderer=template_renderer,
        provider_config_source=config,
        logger=telemetry,
    )
    acknowledgement_service = JourneyAcknowledgementService(renderer=template_renderer)
    differ = IntakeDataDiffer(journey=journey)

    intake_use_case = IntakeUseCase(
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

    registry = DefaultResearchStepRegistry(
        prompts=config.app_config.prompts.research_steps,
        llm=fake_llm,
    )
    research_pipeline = ResearchPipeline(
        steps=list(registry.steps),
        telemetry=telemetry,
        max_concurrent_calls=config.app_config.max_concurrent_research_calls,
        timeout_seconds=config.app_config.research_timeout_seconds,
    )

    synthesis_use_case = SynthesisUseCase(
        llm=fake_llm,
        config=config,
        telemetry=telemetry,
    )

    return BriefGenerationPipeline(
        intake_use_case=intake_use_case,
        research_pipeline=research_pipeline,
        synthesis_use_case=synthesis_use_case,
        storage=storage,
        completeness_checker=completeness_checker,
    )


def _complete_intake_data() -> dict[str, object]:
    """Return a fully populated intake data dict for the production journey."""
    return {
        "first_name": "Alex",
        "brand_name": "Nike",
        "brand_url": "https://nike.com",
        "competitors": ["Adidas", "Puma"],
        "primary_goal": "new customer acquisition",
        "target_customer": "18-34 year old athletes who care about style and performance",
        "creative_directions": {
            "explore": ["authentic athlete stories"],
            "avoid": ["generic celebrity endorsements"],
        },
        "additional_context": "Focus on sustainability messaging",
    }


def _add_intake_fixture(
    fake_llm: FakeLLMAdapter,
    name: str,
    data: dict[str, object],
) -> None:
    """Register a fixture that matches intake extraction prompts."""
    fake_llm._fixtures[name] = {
        "_meta": {
            "match_keywords": [
                "extract",
                "structured",
                "data",
                "from this conversation",
            ],
        },
        "response": data,
    }


class TestFullPipeline:
    """End-to-end pipeline integration tests using production classes."""

    @pytest.mark.asyncio
    async def test_should_generate_complete_brief_for_nike(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """Full pipeline: send message, trigger research, get brief."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            _complete_intake_data(),
        )

        session = ChatSession()
        events = []
        async for event in pipeline.run(session, "Complete Nike intake in one message"):
            events.append(event)

        # Pipeline should have yielded intake, research, synthesis, brief and complete events.
        stages = [e.stage for e in events]
        assert "intake" in stages
        assert "research" in stages
        assert "synthesis" in stages
        assert "brief" in stages
        assert "complete" in stages

        brief = await storage.get_brief(session.session_id)
        assert brief is not None
        assert brief.brand_name == "Nike"
        assert brief.primary_goal != ""
        assert brief.target_customer != ""

        md = BriefMarkdownRenderer().render(brief)
        assert "# Creative Brief:" in md
        assert brief.brand_name in md
        assert "Brief Scout" in md

    @pytest.mark.asyncio
    async def test_should_complete_research_in_under_one_second(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
    ) -> None:
        """Research should complete within 1 second when run in parallel."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            {
                **_complete_intake_data(),
                "target_customer": "18-34 year old athletes",
            },
        )

        session = ChatSession()
        start = time.monotonic()
        events = [e async for e in pipeline.run(session, "Nike brief")]
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"Pipeline took {elapsed:.3f}s, expected < 1.0s"
        assert any(e.stage == "brief" for e in events)

    @pytest.mark.asyncio
    async def test_should_produce_identical_results_across_runs(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
    ) -> None:
        """Multiple identical pipeline runs should produce identical briefs."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            {
                **_complete_intake_data(),
                "target_customer": "18-34 year old athletes",
            },
        )

        briefs: list[str] = []
        for _ in range(10):
            session = ChatSession()
            events = [e async for e in pipeline.run(session, "Nike brief")]
            brief_event = next(e for e in events if e.stage == "brief")
            brief = Brief.model_validate(brief_event.payload["brief"])
            briefs.append(BriefMarkdownRenderer().render(brief))

        assert all(b == briefs[0] for b in briefs), "All runs should produce identical briefs"

    @pytest.mark.asyncio
    async def test_should_persist_session_through_pipeline(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """Session should be persisted at each stage and retrievable."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            {
                **_complete_intake_data(),
                "target_customer": "18-34 year old athletes",
            },
        )

        session = ChatSession()
        _ = [e async for e in pipeline.run(session, "Nike brief")]

        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.intake_data.brand_name == "Nike"
        assert persisted.status == "complete"

    @pytest.mark.asyncio
    async def test_should_handle_single_message_intake(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """All intake info in one message should still produce a brief."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            {
                **_complete_intake_data(),
                "target_customer": "18-34 year old athletes",
            },
        )

        session = ChatSession()
        events = [e async for e in pipeline.run(session, "Complete Nike intake in one message")]

        assert any(e.stage == "brief" for e in events)
        persisted = await storage.get_session(session.session_id)
        assert persisted is not None
        assert persisted.intake_data.brand_name == "Nike"
        assert persisted.status == "complete"

    @pytest.mark.asyncio
    async def test_should_resume_complete_session_idempotently(
        self,
        pipeline: BriefGenerationPipeline,
        fake_llm: FakeLLMAdapter,
        storage: InMemoryStorageAdapter,
    ) -> None:
        """Calling pipeline.run without a message resumes a complete session."""
        _add_intake_fixture(
            fake_llm,
            "intake_complete",
            {
                **_complete_intake_data(),
                "target_customer": "18-34 year old athletes",
            },
        )

        session = ChatSession()
        _ = [e async for e in pipeline.run(session, "Nike brief")]
        await storage.save_session(session)

        resumed_session = await storage.get_session(session.session_id)
        assert resumed_session is not None
        events = [e async for e in pipeline.run(resumed_session)]
        assert any(e.stage == "brief" for e in events)
