"""Shared pytest fixtures for Brief Scout test suite."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import pytest
from pydantic import BaseModel

from brief_scout.domain.models.brief import Brief, CreativeAngle
from brief_scout.domain.models.intake import (
    ChatMessage,
    ChatSession,
    CreativeDirections,
    IntakeData,
)
from brief_scout.domain.models.research import (
    BrandAuditResult,
    CompetitorScanResult,
    CustomerVoiceResult,
    HookMiningResult,
    ResearchBundle,
    TrendPulseResult,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "llm_responses"

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Mock / stub adapters (inline so tests run without full infra layer)
# ---------------------------------------------------------------------------


class _MockTelemetryPort(Protocol):
    """Protocol shape for telemetry — duck-typed so tests Just Work."""

    def log(self, message: str, level: str = "INFO", **kwargs: Any) -> None: ...
    def record_event(self, event: Any) -> None: ...
    def start_span(self, name: str, correlation_id: str = "", **kwargs: Any) -> str: ...
    def end_span(self, span_id: str, **kwargs: Any) -> None: ...
    def get_correlation_id(self) -> str: ...
    def set_correlation_id(self, correlation_id: str) -> None: ...


class LocalFileTelemetryAdapter:
    """Minimal telemetry adapter for tests — writes structured JSON logs to local files."""

    def __init__(self, log_dir: str = "./logs") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._correlation_id: str = ""

    def log(self, message: str, level: str = "INFO", **kwargs: Any) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "message": message,
            "correlation_id": self._correlation_id,
            "data": kwargs,
        }
        log_file = self._log_dir / f"{datetime.now(UTC):%Y-%m-%d}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def record_event(self, event: Any) -> None:
        self.log("event", event_type=getattr(event, "event_type", "unknown"))

    def start_span(self, name: str, correlation_id: str = "", **kwargs: Any) -> str:
        if correlation_id:
            self._correlation_id = correlation_id
        span_id = f"span_{name}_{datetime.now(UTC).timestamp()}"
        self.log("span_start", span_name=name, span_id=span_id, **kwargs)
        return span_id

    def end_span(self, span_id: str, **kwargs: Any) -> None:
        self.log("span_end", span_id=span_id, **kwargs)

    def get_correlation_id(self) -> str:
        return self._correlation_id

    def set_correlation_id(self, correlation_id: str) -> None:
        self._correlation_id = correlation_id


class InMemoryStorageAdapter:
    """In-memory storage for sessions and briefs — NOT persistent across restarts."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._briefs: dict[str, Brief] = {}

    async def save_session(self, session: ChatSession) -> None:
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        self._briefs[session_id] = brief

    async def get_brief(self, session_id: str) -> Brief | None:
        return self._briefs.get(session_id)

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        return list(self._sessions.values())[:limit]


class FakeLLMAdapter:
    """Deterministic LLM adapter that returns fixture-based responses.

    This is the test-fixture version that keeps a call log for verification.
    """

    def __init__(
        self,
        fixture_dir: str = "tests/fixtures/llm_responses",
        default_fixture: str = "default",
        latency_ms: float = 50.0,
        telemetry: Any = None,
    ) -> None:
        self.fixture_dir = Path(fixture_dir)
        self.default_fixture = default_fixture
        self.latency_ms = latency_ms
        self._telemetry = telemetry
        self._call_log: list[dict[str, Any]] = []
        self._fixtures: dict[str, dict[str, Any]] = {}
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        """Walk the fixture directory and index all JSON files."""
        if not self.fixture_dir.exists():
            return
        for json_file in self.fixture_dir.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                rel_parts = json_file.relative_to(self.fixture_dir).parts
                key = "/".join(rel_parts[:-1]) + "/" + json_file.stem
                self._fixtures[key] = data
                self._fixtures[json_file.stem] = data
            except (json.JSONDecodeError, OSError):
                continue

    async def complete(self, prompt: Any, _config: dict[str, Any] | None = None) -> Any:
        """Return a fixture-based LLMResponse."""
        latency = self.latency_ms / 1000.0
        fixture_data = self._match_fixture(prompt)
        meta = fixture_data.get("_meta", {})
        if "latency_ms" in meta:
            latency = meta["latency_ms"] / 1000.0
        await asyncio.sleep(latency)

        response_data = fixture_data.get("response", {})
        response_content = (
            json.dumps(response_data) if isinstance(response_data, dict) else str(response_data)
        )

        class _LLMResponse:
            def __init__(
                self, content: str, provider: str = "fake", latency_ms: float = 0.0
            ) -> None:
                self.content = content
                self.model_used = "fake-model"
                self.provider = provider
                self.tokens_used = len(content.split())
                self.latency_ms = latency_ms
                self.finish_reason = "stop"
                self.metadata: dict[str, Any] = {}

        result = _LLMResponse(
            content=response_content,
            provider="fake",
            latency_ms=latency * 1000,
        )

        call_entry = {
            "prompt_system": getattr(prompt, "system", "")
            if hasattr(prompt, "system")
            else str(prompt),
            "prompt_user": getattr(prompt, "user", "") if hasattr(prompt, "user") else "",
            "fixture_matched": getattr(self, "_last_fixture_key", "unknown"),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._call_log.append(call_entry)

        return result

    async def complete_structured(
        self,
        prompt: Any,
        output_schema: type[T],
        _config: dict[str, Any] | None = None,
    ) -> T:
        """Return a fixture parsed into the requested Pydantic model."""
        fixture_data = self._match_fixture(prompt)
        response_data = fixture_data.get("response", {})
        return output_schema.model_validate(response_data)

    @property
    def provider_name(self) -> str:
        return "fake"

    def _match_fixture(self, prompt: Any) -> dict[str, Any]:
        """Pattern-match prompt content to find appropriate fixture."""
        prompt_text = ""
        if hasattr(prompt, "user"):
            prompt_text = getattr(prompt, "user", "") or ""
        if hasattr(prompt, "system"):
            prompt_text += " " + (getattr(prompt, "system", "") or "")
        if hasattr(prompt, "metadata") and getattr(prompt, "metadata", None):
            meta_hint = getattr(prompt, "metadata", {})
            if "fixture" in meta_hint:
                explicit = self._fixtures.get(meta_hint["fixture"])
                if explicit:
                    self._last_fixture_key = meta_hint["fixture"]
                    return explicit

        prompt_lower = prompt_text.lower()
        best_fixture: dict[str, Any] | None = None
        best_score = 0
        best_key = ""

        for key, fixture in self._fixtures.items():
            meta = fixture.get("_meta", {})
            keywords = meta.get("match_keywords", [])
            if not keywords:
                continue
            score = sum(1 for kw in keywords if kw.lower() in prompt_lower)
            if score > best_score:
                best_score = score
                best_fixture = fixture
                best_key = key

        if best_fixture and best_score > 0:
            self._last_fixture_key = best_key
            return best_fixture

        default = self._fixtures.get(self.default_fixture, {})
        if not default:
            default = self._fixtures.get("default/default", {"_meta": {}, "response": {}})
        self._last_fixture_key = self.default_fixture
        return default

    def get_call_log(self) -> list[dict[str, Any]]:
        return list(self._call_log)

    def clear_call_log(self) -> None:
        self._call_log.clear()


class CompletenessResult:
    """Result of a completeness check."""

    def __init__(
        self,
        is_complete: bool = False,
        missing_fields: list[str] | None = None,
        ready_to_research: bool = False,
        confidence: float = 0.0,
    ) -> None:
        self.is_complete = is_complete
        self.missing_fields = missing_fields or []
        self.ready_to_research = ready_to_research
        self.confidence = confidence


class CompletenessChecker:
    """Evaluates whether collected intake data is sufficient to trigger research."""

    REQUIRED_FIELDS: list[str] = [
        "first_name",
        "brand_name",
        "competitors",
        "primary_goal",
        "target_customer",
    ]

    def __init__(self, telemetry: Any = None) -> None:
        self._telemetry = telemetry

    def check(self, intake_data: IntakeData) -> CompletenessResult:
        """Evaluate intake data completeness."""
        missing: list[str] = []

        if not intake_data.brand_name.strip():
            missing.append("brand_name")
        if len(intake_data.competitors) < 1:
            missing.append("competitors")
        if not intake_data.primary_goal.strip():
            missing.append("primary_goal")
        if not intake_data.target_customer.strip():
            missing.append("target_customer")

        is_complete = len(missing) == 0
        confidence = (
            intake_data.completion_score if hasattr(intake_data, "completion_score") else 0.0
        )

        return CompletenessResult(
            is_complete=is_complete,
            missing_fields=missing,
            ready_to_research=is_complete,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def telemetry(tmp_path: Path) -> Generator[LocalFileTelemetryAdapter, None, None]:
    """Provide a LocalFileTelemetryAdapter writing to a temp directory."""
    log_dir = tmp_path / "test_logs"
    adapter = LocalFileTelemetryAdapter(log_dir=str(log_dir))
    yield adapter


@pytest.fixture
def storage() -> Generator[InMemoryStorageAdapter, None, None]:
    """Provide a fresh InMemoryStorageAdapter."""
    yield InMemoryStorageAdapter()


@pytest.fixture
def fake_llm() -> Generator[FakeLLMAdapter, None, None]:
    """Provide a FakeLLMAdapter loaded with test fixtures.

    Auto-cleanup: clears the call log after each test.
    """
    adapter = FakeLLMAdapter(
        fixture_dir=str(FIXTURE_DIR),
        default_fixture="default",
        latency_ms=10.0,  # Faster for tests
    )
    yield adapter
    adapter.clear_call_log()


@pytest.fixture
def complete_intake_data() -> IntakeData:
    """Return fully populated IntakeData for Nike (all required fields)."""
    return IntakeData(
        first_name="Alex",
        brand_name="Nike",
        brand_url="https://nike.com",
        competitors=["Adidas", "Puma"],
        primary_goal="new customer acquisition",
        target_customer="18-34 year old athletes who care about style and performance",
        creative_directions=CreativeDirections(
            explore=["authentic athlete stories", "community-driven content"],
            avoid=["overly polished studio shots", "generic celebrity endorsements"],
        ),
        additional_context="Focus on sustainability messaging",
    )


@pytest.fixture
def incomplete_intake_data() -> IntakeData:
    """Return IntakeData with just brand_name set."""
    return IntakeData(brand_name="Nike")


@pytest.fixture
def empty_session() -> ChatSession:
    """Return an empty ChatSession."""
    return ChatSession()


@pytest.fixture
def sample_chat_messages() -> list[ChatMessage]:
    """Return a list of sample chat messages representing an intake conversation."""
    return [
        ChatMessage(role="assistant", content="What brand are we building creative for?"),
        ChatMessage(role="user", content="We're building creative for Nike."),
        ChatMessage(role="assistant", content="Who are their top competitors?"),
        ChatMessage(role="user", content="Adidas and Puma."),
        ChatMessage(role="assistant", content="What's the main goal?"),
        ChatMessage(role="user", content="New customer acquisition."),
        ChatMessage(role="assistant", content="Who's the target customer?"),
        ChatMessage(
            role="user", content="18-34 year old athletes who care about style and performance."
        ),
    ]


@pytest.fixture
def sample_research_bundle() -> ResearchBundle:
    """Return a fully populated ResearchBundle with Nike data."""
    return ResearchBundle(
        brand_audit=BrandAuditResult(
            brand_positioning="Nike positions itself as the ultimate performance brand.",
            current_creative_angle="Emotional motivation through athlete stories.",
            key_messages=["Just Do It", "Find Your Greatness"],
            visual_identity_notes="Bold typography, high-contrast black/white.",
            recent_campaigns=["Play New", "Move to Zero"],
        ),
        competitor_scan=CompetitorScanResult(
            competitors=[],
            category_creative_patterns="Athlete endorsements are dominant.",
            whitespace_opportunities=["Mental health + performance", "Everyday athlete"],
        ),
        trend_pulse=TrendPulseResult(
            category_trends=["Sustainable materials", "AI personalization"],
            cultural_moments=["Summer Olympics 2026"],
            emerging_angles=["Anti-perfectionism", "Micro-communities"],
            timing_notes="Q1-Q2: Build Olympic narrative.",
        ),
        customer_voice=CustomerVoiceResult(
            customer_language=["game-changing", "worth every penny"],
            top_desires=["Performance without sacrificing style"],
            top_frustrations=["Price point is steep"],
            emotional_drivers=["Belonging to an active lifestyle tribe"],
            objections=["Too expensive compared to alternatives"],
        ),
        hook_mining=HookMiningResult(
            proven_hook_types=["Transformation stories", "Social proof"],
            emotional_angles=["The first step is the hardest"],
            rational_angles=["Technology breakdown"],
            format_recommendations=["Short-form vertical video"],
            headline_starters=["What [athlete type] know about..."],
        ),
    )


@pytest.fixture
def sample_brief() -> Brief:
    """Return a fully populated Brief for Nike."""
    return Brief(
        brand_name="Nike",
        brand_positioning="Nike positions itself as the ultimate performance brand.",
        primary_goal="new customer acquisition",
        target_customer="18-34 year old athletes who care about style and performance",
        desires=["Performance without sacrificing style"],
        objections=["Too expensive compared to alternatives"],
        competitive_landscape="Adidas and Puma are the main competitors.",
        creative_angles=[
            CreativeAngle(
                name="The Everyday Athlete",
                description="Celebrate real people achieving personal firsts.",
                rationale="Whitespace in grassroots community storytelling.",
            ),
        ],
        proven_hook_types=["Transformation stories"],
        sample_headlines=["What everyday runners know about consistency"],
        creative_mandatories_explore=["Diverse body types"],
        creative_mandatories_avoid=["Elite-only athlete imagery"],
        category_trends=["Sustainable materials"],
    )
