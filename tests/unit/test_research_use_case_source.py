"""Unit tests for the source ResearchUseCase.

Exercises src/brief_scout/application/use_cases/research_use_case.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

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
def complete_intake_data() -> IntakeData:
    """Return fully populated IntakeData."""
    return IntakeData(
        first_name="Alex",
        brand_name="Nike",
        brand_url="https://nike.com",
        competitors=["Adidas", "Puma"],
        primary_goal="new customer acquisition",
        target_customer="18-34 year old athletes who care about style and performance",
    )


@pytest.fixture
def use_case(config: YAMLConfigAdapter, telemetry: LocalFileTelemetryAdapter) -> ResearchUseCase:
    """Provide a ResearchUseCase with a mock LLM."""
    llm = AsyncMock()
    llm.provider_name = "mock"
    return ResearchUseCase(llm=llm, config=config, telemetry=telemetry)


class TestResearchUseCase:
    """Tests for source ResearchUseCase."""

    @pytest.mark.asyncio
    async def test_should_execute_all_five_research_calls(
        self,
        use_case: ResearchUseCase,
        complete_intake_data: IntakeData,
    ) -> None:
        """execute() should call all 5 research areas and return a bundle."""
        llm = cast(AsyncMock, use_case._llm)
        llm.complete_structured.side_effect = [
            BrandAuditResult(brand_positioning="Nike positioning"),
            CompetitorScanResult(category_creative_patterns="patterns"),
            TrendPulseResult(category_trends=["trend"]),
            CustomerVoiceResult(customer_language=["love"]),
            HookMiningResult(proven_hook_types=["hook"]),
        ]

        bundle = await use_case.execute(complete_intake_data)

        assert isinstance(bundle, ResearchBundle)
        assert bundle.brand_audit.brand_positioning == "Nike positioning"
        assert bundle.competitor_scan.category_creative_patterns == "patterns"
        assert bundle.trend_pulse.category_trends == ["trend"]
        assert bundle.customer_voice.customer_language == ["love"]
        assert bundle.hook_mining.proven_hook_types == ["hook"]
        assert bundle.completed_at is not None
        assert llm.complete_structured.call_count == 5

    @pytest.mark.asyncio
    async def test_should_return_defaults_on_failed_call(
        self,
        use_case: ResearchUseCase,
        complete_intake_data: IntakeData,
    ) -> None:
        """A failed research call should return a default instance."""
        llm = cast(AsyncMock, use_case._llm)
        llm.complete_structured.side_effect = [
            BrandAuditResult(brand_positioning="Nike positioning"),
            CompetitorScanResult(),
            TrendPulseResult(),
            CustomerVoiceResult(),
            Exception("hook mining failed"),
        ]

        bundle = await use_case.execute(complete_intake_data)

        assert bundle.brand_audit.brand_positioning == "Nike positioning"
        assert isinstance(bundle.hook_mining, HookMiningResult)

    @pytest.mark.asyncio
    async def test_should_infer_category_from_intake(self) -> None:
        """_infer_category should map known keywords to categories."""
        intake = IntakeData(
            brand_name="SaaS Co",
            target_customer="software buyers",
        )
        category = ResearchUseCase._infer_category(intake)
        assert category == "technology / software"

    def test_should_infer_general_category_by_default(self) -> None:
        """_infer_category should return 'general' when no keywords match."""
        intake = IntakeData(brand_name="Xyz", target_customer="everyone")
        assert ResearchUseCase._infer_category(intake) == "general"

    @pytest.mark.asyncio
    async def test_should_format_prompt_with_placeholders(
        self,
        config: YAMLConfigAdapter,
    ) -> None:
        """_format_prompt should substitute placeholders in user template."""
        template = config.get_prompt_template("research_brand_audit")
        prompt = ResearchUseCase._format_prompt(
            template, brand_name="Nike", brand_url="https://nike.com"
        )

        assert "Nike" in prompt.user
        assert "https://nike.com" in prompt.user
        assert prompt.system == template.system
