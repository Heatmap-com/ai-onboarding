"""Unit tests for ResearchPipeline and research step registry."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from brief_scout.application.services import DefaultResearchStepRegistry
from brief_scout.application.services.research_pipeline import (
    PipelineEvent,
    ResearchPipeline,
)
from brief_scout.application.use_cases.research_use_case import ResearchUseCase
from brief_scout.domain.models import (
    BrandAuditResult,
    CompetitorScanResult,
    CustomerVoiceResult,
    HookMiningResult,
    IntakeData,
    ResearchBundle,
    TrendPulseResult,
)
from brief_scout.domain.models.config import PromptTemplateConfig
from brief_scout.infrastructure.config.yaml_config_adapter import YAMLConfigAdapter
from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)

if TYPE_CHECKING:
    from pathlib import Path


class FakeStep:
    """A deterministic research step for testing."""

    def __init__(self, name: str, result: object) -> None:
        self.name = name
        self._result = result

    async def execute(self, _intake_data: IntakeData) -> object:
        return self._result


class FailingStep:
    """A research step that always raises."""

    name = "failing"

    async def execute(self, _intake_data: IntakeData) -> None:
        raise RuntimeError("step failed")


class SlowStep:
    """A research step that sleeps."""

    def __init__(self, name: str, delay: float) -> None:
        self.name = name
        self._delay = delay

    async def execute(self, _intake_data: IntakeData) -> BrandAuditResult:
        await asyncio.sleep(self._delay)
        return BrandAuditResult(brand_positioning="ok")


@pytest.fixture
def telemetry(tmp_path: Path) -> LocalFileTelemetryAdapter:
    """Provide a telemetry adapter writing to a temp directory."""
    return LocalFileTelemetryAdapter(log_dir=str(tmp_path / "logs"))


@pytest.fixture
def config() -> YAMLConfigAdapter:
    """Provide the real YAML config adapter."""
    return YAMLConfigAdapter(config_dir="config", env="development")


@pytest.fixture
def complete_intake_data() -> IntakeData:
    """Return fully populated IntakeData."""
    return IntakeData(
        first_name="Alex",
        brand_name="Nike",
        brand_url="https://nike.com",
        competitors=["Adidas", "Puma"],
        primary_goal="new customer acquisition",
        target_customer="18-34 year old athletes",
    )


@pytest.fixture
def registry(
    config: YAMLConfigAdapter,
) -> DefaultResearchStepRegistry:
    """Provide the default research step registry with a mock LLM."""
    llm = AsyncMock()
    llm.provider_name = "mock"
    return DefaultResearchStepRegistry(
        prompts=config.app_config.prompts.research_steps,
        llm=llm,
    )


@pytest.fixture
def use_case(
    registry: DefaultResearchStepRegistry,
    telemetry: LocalFileTelemetryAdapter,
) -> ResearchUseCase:
    """Provide a ResearchUseCase wired to the default registry."""
    return ResearchUseCase(registry=registry, telemetry=telemetry)


class TestResearchPipeline:
    """Tests for the research pipeline execution and streaming."""

    @pytest.mark.asyncio
    async def test_execute_returns_bundle(self) -> None:
        """execute() should collect all step results into a ResearchBundle."""
        steps = [
            FakeStep("brand_audit", BrandAuditResult(brand_positioning="Nike")),
            FakeStep("competitor_scan", CompetitorScanResult()),
        ]
        pipeline = ResearchPipeline(steps=steps)
        bundle = await pipeline.execute(IntakeData())
        assert isinstance(bundle, ResearchBundle)
        assert bundle.results["brand_audit"].brand_positioning == "Nike"

    @pytest.mark.asyncio
    async def test_execute_ignores_failed_steps(self) -> None:
        """Failed steps should be skipped rather than abort the pipeline."""
        steps = [
            FakeStep("brand_audit", BrandAuditResult(brand_positioning="Nike")),
            FailingStep(),
        ]
        pipeline = ResearchPipeline(steps=steps)
        bundle = await pipeline.execute(IntakeData())
        assert "brand_audit" in bundle.results
        assert "failing" not in bundle.results

    @pytest.mark.asyncio
    async def test_stream_yields_progress_events(self) -> None:
        """stream() should emit started, per-step, and complete events."""
        steps = [FakeStep("brand_audit", BrandAuditResult())]
        pipeline = ResearchPipeline(steps=steps)
        events = [event async for event in pipeline.stream(IntakeData())]
        stages = [e.stage for e in events]
        assert stages == ["research", "research_step", "research"]
        assert events[1].status == "complete"
        assert events[1].payload["name"] == "brand_audit"

    @pytest.mark.asyncio
    async def test_stream_reports_failed_step(self) -> None:
        """stream() should emit a failed event for a failing step."""
        steps = [FailingStep()]
        pipeline = ResearchPipeline(steps=steps)
        events = [event async for event in pipeline.stream(IntakeData())]
        failed_event = next(e for e in events if e.stage == "research_step")
        assert failed_event.status == "failed"
        assert "step failed" in failed_event.payload["error"]

    @pytest.mark.asyncio
    async def test_max_concurrent_calls_limits_concurrency(self) -> None:
        """Semaphore should cap the number of simultaneously running steps."""
        steps = [
            SlowStep("one", 0.05),
            SlowStep("two", 0.05),
            SlowStep("three", 0.05),
        ]
        pipeline = ResearchPipeline(steps=steps, max_concurrent_calls=1)
        running = 0
        max_running = 0

        class TrackingStep:
            name = "tracking"

            async def execute(self, _intake_data: IntakeData) -> BrandAuditResult:
                nonlocal running, max_running
                running += 1
                max_running = max(max_running, running)
                await asyncio.sleep(0.01)
                running -= 1
                return BrandAuditResult()

        pipeline2 = ResearchPipeline(
            steps=[TrackingStep(), TrackingStep()],
            max_concurrent_calls=1,
        )
        await pipeline2.execute(IntakeData())
        assert max_running == 1

        bundle = await pipeline.execute(IntakeData())
        assert len(bundle.results) == 3

    @pytest.mark.asyncio
    async def test_timeout_fails_slow_step(self) -> None:
        """Steps exceeding timeout_seconds should fail gracefully."""
        steps = [SlowStep("slow", 0.5)]
        pipeline = ResearchPipeline(steps=steps, timeout_seconds=0.01)
        bundle = await pipeline.execute(IntakeData())
        assert "slow" not in bundle.results

    def test_pipeline_event_defaults(self) -> None:
        """PipelineEvent should have sensible defaults."""
        event = PipelineEvent()
        assert event.stage == ""
        assert event.status == ""
        assert event.payload == {}


class TestResearchStepRegistry:
    """Tests for the default research step registry and step execution."""

    @pytest.mark.asyncio
    async def test_call_brand_audit(
        self,
        registry: DefaultResearchStepRegistry,
        complete_intake_data: IntakeData,
    ) -> None:
        """brand_audit step should return a BrandAuditResult."""
        step = next(s for s in registry.steps if s.name == "brand_audit")
        llm = registry._llm
        llm.complete_structured.return_value = BrandAuditResult(brand_positioning="Nike")
        result = await step.execute(complete_intake_data)
        assert isinstance(result, BrandAuditResult)
        assert result.brand_positioning == "Nike"

    @pytest.mark.asyncio
    async def test_call_competitor_scan(
        self,
        registry: DefaultResearchStepRegistry,
        complete_intake_data: IntakeData,
    ) -> None:
        """competitor_scan step should return a CompetitorScanResult."""
        step = next(s for s in registry.steps if s.name == "competitor_scan")
        llm = registry._llm
        llm.complete_structured.return_value = CompetitorScanResult(
            category_creative_patterns="patterns",
        )
        result = await step.execute(complete_intake_data)
        assert isinstance(result, CompetitorScanResult)

    @pytest.mark.asyncio
    async def test_call_trend_pulse(
        self,
        registry: DefaultResearchStepRegistry,
        complete_intake_data: IntakeData,
    ) -> None:
        """trend_pulse step should return a TrendPulseResult."""
        step = next(s for s in registry.steps if s.name == "trend_pulse")
        llm = registry._llm
        llm.complete_structured.return_value = TrendPulseResult(category_trends=["trend"])
        result = await step.execute(complete_intake_data)
        assert isinstance(result, TrendPulseResult)

    @pytest.mark.asyncio
    async def test_call_customer_voice(
        self,
        registry: DefaultResearchStepRegistry,
        complete_intake_data: IntakeData,
    ) -> None:
        """customer_voice step should return a CustomerVoiceResult."""
        step = next(s for s in registry.steps if s.name == "customer_voice")
        llm = registry._llm
        llm.complete_structured.return_value = CustomerVoiceResult(
            customer_language=["love"],
        )
        result = await step.execute(complete_intake_data)
        assert isinstance(result, CustomerVoiceResult)

    @pytest.mark.asyncio
    async def test_call_hook_mining(
        self,
        registry: DefaultResearchStepRegistry,
        complete_intake_data: IntakeData,
    ) -> None:
        """hook_mining step should return a HookMiningResult."""
        step = next(s for s in registry.steps if s.name == "hook_mining")
        llm = registry._llm
        llm.complete_structured.return_value = HookMiningResult(
            proven_hook_types=["hook"],
        )
        result = await step.execute(complete_intake_data)
        assert isinstance(result, HookMiningResult)

    def test_build_pipeline_requires_all_steps(self, use_case: ResearchUseCase) -> None:
        """_build_pipeline should produce all five default steps."""
        pipeline = use_case._build_pipeline()
        step_names = {step.name for step in pipeline._steps}
        assert step_names == {
            "brand_audit",
            "competitor_scan",
            "trend_pulse",
            "customer_voice",
            "hook_mining",
        }

    def test_step_templates_are_prompt_configs(self, config: YAMLConfigAdapter) -> None:
        """Each configured step template should be a PromptTemplateConfig."""
        prompts = config.app_config.prompts.research_steps
        for name in (
            "brand_audit",
            "competitor_scan",
            "trend_pulse",
            "customer_voice",
            "hook_mining",
        ):
            assert isinstance(prompts[name], PromptTemplateConfig)
