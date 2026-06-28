"""Tests for the demo journey fixture integration with FakeLLM."""

from __future__ import annotations

import pytest

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.models import IntakeData
from brief_scout.domain.ports.llm_port import Prompt
from brief_scout.infrastructure.llm.fake_llm_adapter import FakeLLMAdapter


@pytest.fixture
def adapter() -> FakeLLMAdapter:
    """Provide a FakeLLM adapter configured with the demo journey."""
    return FakeLLMAdapter(
        fixture_dir="tests/fixtures/llm_responses",
        demo_journey_path="tests/fixtures/demo_journey.yaml",
        latency_ms=0.0,
    )


@pytest.mark.asyncio
async def test_demo_turn_returns_cumulative_data(adapter: FakeLLMAdapter) -> None:
    """Demo turn config should return the cumulative IntakeData for that turn."""
    prompt = Prompt(system="extract", user="conversation")
    result = await adapter.complete_structured(
        prompt,
        IntakeData,
        config={"demo_turn": 4},
    )

    assert result.first_name == "Alex"
    assert result.brand_name == "Nike"
    assert "Adidas" in result.competitors
    assert result.primary_goal == "new customer acquisition"
    assert "18-34" in result.target_customer


@pytest.mark.asyncio
async def test_demo_turn_last_turn_is_complete(adapter: FakeLLMAdapter) -> None:
    """The final demo turn should include creative directions and additional context."""
    prompt = Prompt(system="extract", user="conversation")
    result = await adapter.complete_structured(
        prompt,
        IntakeData,
        config={"demo_turn": 5},
    )

    assert "authentic athlete stories" in result.creative_directions.explore
    assert "generic celebrity endorsements" in result.creative_directions.avoid
    assert "sustainability" in result.additional_context


@pytest.mark.asyncio
async def test_demo_turn_ignored_without_path() -> None:
    """An adapter without demo_journey_path should ignore demo_turn and fall back."""
    adapter_no_demo = FakeLLMAdapter(
        fixture_dir="tests/fixtures/llm_responses",
        latency_ms=0.0,
    )
    prompt = Prompt(system="extract", user="conversation")

    # Without a demo journey path, demo_turn is ignored and fixture matching runs.
    # The default fixture has empty content, so structured completion now raises
    # to stay consistent with real adapters (LSP).
    with pytest.raises(LLMCallError):
        await adapter_no_demo.complete_structured(
            prompt,
            IntakeData,
            config={"demo_turn": 3},
        )
