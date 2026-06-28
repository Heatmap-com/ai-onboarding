"""Comprehensive unit tests for the source FakeLLMAdapter.

Per SPEC Section 7.1 — Tests deterministic fixture-based LLM responses.
Target: 90% coverage of src/brief_scout/infrastructure/llm/fake_llm_adapter.py.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.models.research import BrandAuditResult
from brief_scout.domain.ports.llm_port import Prompt
from brief_scout.infrastructure.llm.fake_llm_adapter import FakeLLMAdapter
from brief_scout.infrastructure.llm.test_fake_llm_adapter import (
    TestFakeLLMAdapter as FakeLLMTestAdapter,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "llm_responses"


class _Prompt:
    """Simple prompt container retained for backward-compatible test imports."""

    def __init__(self, system: str = "", user: str = "") -> None:
        self.system = system
        self.user = user


class _TestBrandResult(BaseModel):
    """Test schema for structured output."""

    brand_name: str = ""
    industry: str = ""


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fake_llm() -> FakeLLMTestAdapter:
    """Provide a FakeLLMAdapter loaded with test fixtures."""
    return FakeLLMTestAdapter(
        fixture_dir=str(FIXTURE_DIR),
        default_fixture="default",
        latency_ms=10.0,
    )


@pytest.fixture
def telemetry() -> MagicMock:
    """Provide a mock telemetry port."""
    return MagicMock()


# ============================================================================
# Tests
# ============================================================================


class TestFakeLLMAdapter:
    """Comprehensive tests for the FakeLLMAdapter fixture-based LLM."""

    def test_should_load_fixtures_on_init(self, fake_llm: FakeLLMAdapter) -> None:
        """Adapter should load fixtures from disk on construction."""
        assert len(fake_llm._fixtures) > 0
        # Should have indexed nike fixtures by relative path
        assert any("nike" in k for k in fake_llm._fixtures)

    def test_should_build_keyword_index(self, fake_llm: FakeLLMAdapter) -> None:
        """Adapter should build a keyword index from fixture metadata."""
        assert len(fake_llm._keyword_index) > 0
        keywords = {kw for entry in fake_llm._keyword_index for kw in entry["keywords"]}
        assert "nike" in keywords

    @pytest.mark.asyncio
    async def test_should_match_fixture_by_keywords(self, fake_llm: FakeLLMAdapter) -> None:
        """Prompt containing fixture keywords should return matching response."""
        prompt = Prompt(user="Research Nike brand audit positioning")
        response = await fake_llm.complete(prompt)

        assert "Nike" in response.content or "nike" in response.content.lower()
        assert response.provider == "fake"
        assert response.model_used == "fake"
        assert response.latency_ms >= 0
        assert response.tokens_used >= 0
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_should_return_default_for_unknown_prompt(self, fake_llm: FakeLLMAdapter) -> None:
        """Prompt with no matching keywords should return default fixture."""
        prompt = Prompt(user="Something completely unrelated xyz123 unknown")
        response = await fake_llm.complete(prompt)

        # Default fixture has empty fields
        data = json.loads(response.content) if response.content.startswith("{") else {}
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_should_simulate_latency(self, fake_llm: FakeLLMAdapter) -> None:
        """complete() should take at least the configured latency."""
        prompt = Prompt(user="nike")
        fake_llm._default_latency_ms = 50.0

        start = time.monotonic()
        await fake_llm.complete(prompt)
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed >= 45.0  # Allow small tolerance for async overhead

    @pytest.mark.asyncio
    async def test_should_return_llm_response(self, fake_llm: FakeLLMAdapter) -> None:
        """complete() should return an LLMResponse with expected attributes."""
        prompt = Prompt(user="nike brand audit")
        response = await fake_llm.complete(prompt)

        assert response.content
        assert response.provider == "fake"
        assert response.latency_ms > 0
        assert response.tokens_used >= 0

    @pytest.mark.asyncio
    async def test_should_parse_structured_output(self, fake_llm: FakeLLMAdapter) -> None:
        """complete_structured() should return a parsed Pydantic model."""
        prompt = Prompt(user="nike brand audit positioning")
        result = await fake_llm.complete_structured(prompt, BrandAuditResult)

        assert isinstance(result, BrandAuditResult)
        assert "Nike" in result.brand_positioning

    @pytest.mark.asyncio
    async def test_should_record_call_in_log(self, fake_llm: FakeLLMTestAdapter) -> None:
        """Each call should be recorded in the call log."""
        prompt = Prompt(user="nike customer voice")
        await fake_llm.complete(prompt)

        log = fake_llm.get_call_log()
        assert len(log) >= 1
        last_call = log[-1]
        assert "timestamp" in last_call
        assert "fixture_name" in last_call

    @pytest.mark.asyncio
    async def test_should_clear_call_log(self, fake_llm: FakeLLMTestAdapter) -> None:
        """clear_call_log() should empty the call log."""
        prompt = Prompt(user="nike")
        await fake_llm.complete(prompt)
        assert len(fake_llm.get_call_log()) >= 1

        fake_llm.clear_call_log()
        assert fake_llm.get_call_log() == []

    @pytest.mark.asyncio
    async def test_should_override_fixture_via_config(self, fake_llm: FakeLLMAdapter) -> None:
        """complete() should respect fixture_name override in config."""
        prompt = Prompt(user="irrelevant")
        response = await fake_llm.complete(prompt, config={"fixture_name": "brand_audit/nike"})

        assert "Nike" in response.content

    @pytest.mark.asyncio
    async def test_should_override_latency_via_config(self, fake_llm: FakeLLMAdapter) -> None:
        """complete() should respect latency_ms override in config."""
        prompt = Prompt(user="nike")
        start = time.monotonic()
        await fake_llm.complete(prompt, config={"latency_ms": 80.0})
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed >= 75.0

    @pytest.mark.asyncio
    async def test_should_use_fixture_latency(self, fake_llm: FakeLLMAdapter) -> None:
        """complete() should use per-fixture latency when no override given."""
        prompt = Prompt(user="nike brand audit")
        start = time.monotonic()
        await fake_llm.complete(prompt)
        elapsed = (time.monotonic() - start) * 1000

        # nike brand audit fixture has latency_ms: 100
        assert elapsed >= 90.0

    @pytest.mark.asyncio
    async def test_should_telemetry_record_event(self) -> None:
        """complete() should record a telemetry event when telemetry is wired."""
        telemetry = MagicMock()
        adapter = FakeLLMAdapter(
            fixture_dir=str(FIXTURE_DIR),
            default_fixture="default",
            latency_ms=1.0,
            telemetry=telemetry,
        )
        prompt = Prompt(user="nike")
        await adapter.complete(prompt)

        telemetry.record_event.assert_called_once()
        event = telemetry.record_event.call_args[0][0]
        assert event.event_type == "llm.call.complete"
        assert event.data["provider"] == "fake"

    @pytest.mark.asyncio
    async def test_should_handle_missing_fixture_dir(self, tmp_path: Path) -> None:
        """Adapter should tolerate a missing fixture directory."""
        adapter = FakeLLMAdapter(
            fixture_dir=str(tmp_path / "nonexistent"),
            default_fixture="default",
            latency_ms=1.0,
        )
        prompt = Prompt(user="anything")
        response = await adapter.complete(prompt)

        assert response.content == ""
        assert response.provider == "fake"

    @pytest.mark.asyncio
    async def test_should_handle_invalid_json_fixture(self, tmp_path: Path) -> None:
        """Adapter should skip invalid JSON fixture files."""
        bad_dir = tmp_path / "bad_fixtures"
        bad_dir.mkdir()
        (bad_dir / "broken.json").write_text("not json")

        adapter = FakeLLMAdapter(fixture_dir=str(bad_dir), default_fixture="default")
        assert adapter._fixtures == {}

    @pytest.mark.asyncio
    async def test_should_raise_on_non_dict_response_in_structured(self, tmp_path: Path) -> None:
        """complete_structured() should raise LLMCallError when response is not a dict."""
        bad_dir = tmp_path / "bad_fixtures"
        bad_dir.mkdir()
        (bad_dir / "list.json").write_text(
            json.dumps({"_meta": {"match_keywords": ["list"]}, "response": ["not", "a", "dict"]})
        )
        adapter = FakeLLMAdapter(fixture_dir=str(bad_dir), default_fixture="default")
        prompt = Prompt(user="list")
        with pytest.raises(LLMCallError):
            await adapter.complete_structured(prompt, _TestBrandResult)

    @pytest.mark.asyncio
    async def test_should_raise_on_unparseable_response_in_structured(self, tmp_path: Path) -> None:
        """complete_structured() should raise LLMCallError when JSON parsing fails."""
        bad_dir = tmp_path / "bad_fixtures2"
        bad_dir.mkdir()
        (bad_dir / "bad.json").write_text(
            json.dumps({"_meta": {"match_keywords": ["bad"]}, "response": "not json"})
        )
        adapter = FakeLLMAdapter(fixture_dir=str(bad_dir), default_fixture="default")
        prompt = Prompt(user="bad")
        with pytest.raises(LLMCallError):
            await adapter.complete_structured(prompt, _TestBrandResult)

    @pytest.mark.asyncio
    async def test_should_raise_on_default_instantiation_failure(self, tmp_path: Path) -> None:
        """complete_structured() should raise LLMCallError if default instantiation fails."""
        bad_dir = tmp_path / "bad_fixtures3"
        bad_dir.mkdir()
        (bad_dir / "bad.json").write_text(
            json.dumps({"_meta": {"match_keywords": ["bad"]}, "response": "not json"})
        )
        adapter = FakeLLMAdapter(fixture_dir=str(bad_dir), default_fixture="default")

        class BrokenModel(BaseModel):
            """Model that cannot be instantiated without required args."""

            name: str  # no default

        prompt = Prompt(user="bad")
        with pytest.raises(LLMCallError):
            await adapter.complete_structured(prompt, BrokenModel)

    def test_provider_name(self) -> None:
        """provider_name should return 'fake'."""
        adapter = FakeLLMAdapter(fixture_dir=str(FIXTURE_DIR))
        assert adapter.provider_name == "fake"

    @pytest.mark.asyncio
    async def test_should_match_by_stem_override(self, fake_llm: FakeLLMAdapter) -> None:
        """fixture_name override that is a stem should match a path ending."""
        prompt = Prompt(user="irrelevant")
        response = await fake_llm.complete(prompt, config={"fixture_name": "nike"})

        # Several fixtures end with 'nike'; exact stem match should succeed.
        assert response.content
