"""Unit tests for the source SynthesisUseCase.

Exercises src/brief_scout/application/use_cases/synthesis_use_case.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from brief_scout.application.use_cases.synthesis_use_case import SynthesisUseCase
from brief_scout.domain.errors import SynthesisError
from brief_scout.domain.models import (
    BrandAuditResult,
    Brief,
    CompetitorScanResult,
    CreativeAngle,
    CustomerVoiceResult,
    HookMiningResult,
    IntakeData,
    ResearchBundle,
    TrendPulseResult,
)
from brief_scout.infrastructure.config.yaml_config_adapter import (
    YAMLConfigAdapter,
)
from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)


@pytest.fixture
def telemetry(tmp_path: Path) -> LocalFileTelemetryAdapter:
    """Provide a telemetry adapter writing to a temp directory."""
    return LocalFileTelemetryAdapter(log_dir=str(tmp_path / "logs"))


@pytest.fixture
def config() -> YAMLConfigAdapter:
    """Provide the real YAML config adapter."""
    return YAMLConfigAdapter(config_dir="config", env="development")


@pytest.fixture
def use_case(config: YAMLConfigAdapter, telemetry: LocalFileTelemetryAdapter) -> SynthesisUseCase:
    """Provide a SynthesisUseCase with a mock LLM."""
    llm = AsyncMock()
    llm.provider_name = "mock"
    return SynthesisUseCase(llm=llm, config=config, telemetry=telemetry)


@pytest.fixture
def complete_intake_data() -> IntakeData:
    """Return fully populated IntakeData."""
    return IntakeData(
        first_name="Alex",
        brand_name="Nike",
        brand_url="https://nike.com",
        competitors=["Adidas", "Puma"],
        primary_goal="new customer acquisition",
        target_customer="18-34 athletes",
    )


@pytest.fixture
def research_bundle() -> ResearchBundle:
    """Return a populated ResearchBundle."""
    return ResearchBundle(
        brand_audit=BrandAuditResult(brand_positioning="Nike positioning"),
        competitor_scan=CompetitorScanResult(category_creative_patterns="patterns"),
        trend_pulse=TrendPulseResult(category_trends=["trend"]),
        customer_voice=CustomerVoiceResult(customer_language=["love"]),
        hook_mining=HookMiningResult(proven_hook_types=["hook"]),
    )


class TestSynthesisUseCase:
    """Tests for source SynthesisUseCase."""

    @pytest.mark.asyncio
    async def test_should_synthesize_brief(
        self,
        use_case: SynthesisUseCase,
        complete_intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> None:
        """execute() should return a Brief with sources attached."""
        expected_brief = Brief(
            brand_name="Nike",
            primary_goal="new customer acquisition",
            creative_angles=[CreativeAngle(name="Angle 1", description="desc")],
        )
        llm = cast(AsyncMock, use_case._llm)
        llm.complete_structured.return_value = expected_brief

        brief = await use_case.execute(complete_intake_data, research_bundle)

        assert isinstance(brief, Brief)
        assert brief.brand_name == "Nike"
        assert brief.sources is research_bundle
        llm.complete_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_build_prompt_with_intake_and_research_json(
        self,
        use_case: SynthesisUseCase,
        complete_intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> None:
        """_build_synthesis_prompt should include serialized intake and research."""
        prompt = use_case._build_synthesis_prompt(complete_intake_data, research_bundle)

        assert "Nike" in prompt.user
        assert "brand_audit" in prompt.user
        assert prompt.system

    @pytest.mark.asyncio
    async def test_should_raise_synthesis_error_on_failure(
        self,
        use_case: SynthesisUseCase,
        complete_intake_data: IntakeData,
        research_bundle: ResearchBundle,
    ) -> None:
        """execute() should raise SynthesisError when LLM call fails."""
        llm = cast(AsyncMock, use_case._llm)
        llm.complete_structured.side_effect = ValueError("boom")

        with pytest.raises(SynthesisError):
            await use_case.execute(complete_intake_data, research_bundle)
