"""Unit tests for the token-tracking LLM wrapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from brief_scout.domain.models import IntakeData
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.infrastructure.llm.token_tracking_adapter import (
    TokenTrackingLLM,
    TokenUsageRecord,
    _rates_for,
)


def test_rates_for_unknown_model_falls_back_to_gpt_4o_mini() -> None:
    """_rates_for should return gpt-4o-mini pricing for unknown models."""
    assert _rates_for("some-unknown-model") == (0.15, 0.60)


def test_rates_for_known_model() -> None:
    """_rates_for should match known model substrings."""
    assert _rates_for("gpt-4o") == (2.50, 10.00)
    assert _rates_for("claude-3-haiku") == (0.25, 1.25)


def test_token_usage_record_cost() -> None:
    """A TokenUsageRecord should estimate cost from token counts and rates."""
    record = TokenUsageRecord(
        call_number=1,
        provider="fake",
        model="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    # 0.15 + 0.60 = 0.75 USD per 1M tokens each.
    assert record.estimated_cost_usd == pytest.approx(0.75)
    assert record.total_tokens == 2_000_000


def test_token_usage_summary_includes_records() -> None:
    """TokenUsage.summary should include headers, records, and totals."""
    tracker = TokenTrackingLLM(AsyncMock(), model="gpt-4o-mini")
    tracker._usage.records.append(
        TokenUsageRecord(
            call_number=1,
            provider="fake",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
        ),
    )
    summary = tracker.token_usage.summary()
    assert "Call" in summary
    assert "TOTAL" in summary
    assert "150" in summary


@pytest.mark.asyncio
async def test_complete_records_token_usage() -> None:
    """complete() should delegate and record input/output token counts."""
    adapter = AsyncMock()
    adapter.provider_name = "fake"
    adapter.complete.return_value = LLMResponse(content="hello world")

    tracker = TokenTrackingLLM(adapter, model="gpt-4o-mini")
    prompt = Prompt(system="system", user="user")
    response = await tracker.complete(prompt)

    assert response.content == "hello world"
    assert len(tracker.token_usage.records) == 1
    record = tracker.token_usage.records[0]
    assert record.provider == "fake"
    assert record.model == "gpt-4o-mini"
    assert record.input_tokens > 0
    assert record.output_tokens > 0
    adapter.complete.assert_awaited_once_with(prompt, None)


@pytest.mark.asyncio
async def test_complete_structured_records_token_usage() -> None:
    """complete_structured() should delegate and record token counts."""
    adapter = AsyncMock()
    adapter.provider_name = "fake"
    adapter.complete_structured.return_value = IntakeData(brand_name="Nike")

    tracker = TokenTrackingLLM(adapter, model="gpt-4o-mini")
    prompt = Prompt(system="system", user="user")
    result = await tracker.complete_structured(prompt, IntakeData)

    assert result.brand_name == "Nike"
    assert len(tracker.token_usage.records) == 1
    record = tracker.token_usage.records[0]
    assert record.input_tokens > 0
    assert record.output_tokens > 0
    adapter.complete_structured.assert_awaited_once_with(prompt, IntakeData, None)


def test_count_text_fallback_without_encoder(monkeypatch: Any) -> None:
    """_count_text should fall back to a character heuristic when no encoder."""
    tracker = TokenTrackingLLM(AsyncMock(), model="gpt-4o-mini")
    monkeypatch.setattr(tracker, "_encoder", None)
    # 40 characters -> 10 tokens with the heuristic.
    assert tracker._count_text("x" * 40) == 10
    # Empty string still returns at least 1 token.
    assert tracker._count_text("") == 1
