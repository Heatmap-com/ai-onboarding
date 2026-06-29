"""Fake LLM Adapter — deterministic, fixture-based LLM responses.

This is the PRIMARY LLM adapter for the Brief Scout MVP. It simulates
LLM responses by loading JSON fixture files and matching them against
prompt content using keyword scoring. Zero network calls, zero cost,
100% deterministic.

The adapter is now a thin coordinator over focused collaborators:
  - FixtureRepository: recursive fixture loading and keyword indexing.
  - DemoJourneyPlayer: demo-journey YAML turn synthesis.
  - FixtureMatcher: prompt-to-fixture matching strategies.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.domain.ports.telemetry_port import LogLevel, TelemetryEvent
from brief_scout.infrastructure.llm.demo_journey_player import DemoJourneyPlayer
from brief_scout.infrastructure.llm.fixture_matcher import FixtureMatcher
from brief_scout.infrastructure.llm.fixture_repository import FixtureRepository
from brief_scout.infrastructure.llm.shared_json_utils import (
    strip_markdown_code_blocks,
)

if TYPE_CHECKING:
    from brief_scout.domain.ports.event_recorder_port import EventRecorder
    from brief_scout.domain.ports.logger_port import LoggerPort

T = TypeVar("T", bound=BaseModel)


class FakeLLMAdapter:
    """Deterministic LLM adapter that returns fixture-based responses."""

    def __init__(
        self,
        fixture_dir: str = "tests/fixtures/llm_responses",
        default_fixture: str = "default",
        latency_ms: float = 50.0,
        telemetry: LoggerPort | EventRecorder | None = None,
        demo_journey_path: str | None = None,
        repository: FixtureRepository | None = None,
        demo_player: DemoJourneyPlayer | None = None,
        matcher: FixtureMatcher | None = None,
        **_kwargs: Any,
    ) -> None:
        """Initialize the Fake LLM Adapter.

        Args:
            fixture_dir: Directory containing JSON fixture files.
            default_fixture: Name of the default fixture to use when no keywords match.
            latency_ms: Default simulated latency in milliseconds.
            telemetry: Optional logger/event recorder port.
            demo_journey_path: Optional YAML file with cumulative demo turn data.
            repository: Optional FixtureRepository (used by tests).
            demo_player: Optional DemoJourneyPlayer (used by tests).
            matcher: Optional FixtureMatcher (used by tests).
            **_kwargs: Ignored generic constructor arguments from the factory.
        """
        self._telemetry = telemetry
        self._repository = repository or FixtureRepository(
            fixture_dir=fixture_dir,
            default_fixture_name=default_fixture,
            default_latency_ms=latency_ms,
            logger=cast("LoggerPort | None", telemetry),
        )
        self._demo_player = demo_player or DemoJourneyPlayer(
            demo_journey_path=demo_journey_path,
            default_latency_ms=latency_ms,
            logger=cast("LoggerPort | None", telemetry),
        )
        self._matcher = matcher or FixtureMatcher(self._repository, self._demo_player)
        self._default_fixture_name = default_fixture
        self._default_latency_ms = latency_ms

    @property
    def _fixtures(self) -> dict[str, dict[str, Any]]:
        """Backward-compatible accessor for tests."""
        return self._repository.fixtures

    @property
    def _keyword_index(self) -> list[dict[str, Any]]:
        """Backward-compatible accessor for tests."""
        return self._repository.keyword_index

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "fake"

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Return a fixture-based response."""
        merged_config = config or {}
        override_latency: float | None = merged_config.get("latency_ms")
        override_fixture: str | None = merged_config.get("fixture_name")
        demo_turn: int | None = merged_config.get("demo_turn")

        fixture_name, fixture_data, matched_latency = self._matcher.match(
            prompt,
            override_fixture=override_fixture,
            demo_turn=demo_turn,
        )
        latency_ms = override_latency if override_latency is not None else matched_latency

        await asyncio.sleep(latency_ms / 1000.0)

        response_content = fixture_data.get("response", "")
        if not isinstance(response_content, str):
            response_content = str(response_content)

        response = LLMResponse(
            content=response_content,
            model_used="fake",
            provider="fake",
            tokens_used=len(response_content.split()),
            latency_ms=latency_ms,
            finish_reason="stop",
            metadata={
                "provider": "fake",
                "model": "fake",
                "tokens_used": len(response_content.split()),
                "latency_ms": latency_ms,
                "provider_metadata": {
                    "fixture_name": fixture_name,
                    "fixture_dir": str(self._repository.fixture_dir),
                },
            },
        )

        if self._telemetry is not None and hasattr(self._telemetry, "record_event"):
            self._telemetry.record_event(
                TelemetryEvent(
                    event_type="llm.call.complete",
                    data={
                        "provider": "fake",
                        "fixture_name": fixture_name,
                        "latency_ms": latency_ms,
                    },
                )
            )

        return response

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Return a fixture parsed into the requested Pydantic model.

        Matches the fixture directly (without going through ``complete()``)
        so that dict fixture responses can be validated as structured data.

        Raises:
            LLMCallError: If JSON parsing or Pydantic validation fails.
        """
        merged_config = config or {}
        override_fixture: str | None = merged_config.get("fixture_name")
        demo_turn: int | None = merged_config.get("demo_turn")

        _fixture_name, fixture_data, _latency = self._matcher.match(
            prompt,
            override_fixture=override_fixture,
            demo_turn=demo_turn,
        )

        response_content = fixture_data.get("response", "")
        if isinstance(response_content, dict):
            if not response_content:
                raise LLMCallError(
                    message=f"Fixture response is an empty object for {output_schema.__name__}",
                    provider="fake",
                    retryable=False,
                )
            try:
                return output_schema(**response_content)
            except Exception as validation_exc:
                raise LLMCallError(
                    message=f"Failed to validate fixture for {output_schema.__name__}: {validation_exc}",
                    provider="fake",
                    retryable=False,
                ) from validation_exc

        if not isinstance(response_content, str):
            raise LLMCallError(
                message=f"Fixture response is not a JSON object for {output_schema.__name__}",
                provider="fake",
                retryable=False,
            )

        raw_content = strip_markdown_code_blocks(response_content)
        if not raw_content:
            raise LLMCallError(
                message=f"Fixture response is empty for {output_schema.__name__}",
                provider="fake",
                retryable=False,
                raw_content=response_content[:500],
            )

        try:
            parsed_data = json.loads(raw_content)
        except Exception as parse_exc:
            raise LLMCallError(
                message=f"Failed to parse fixture JSON for {output_schema.__name__}: {parse_exc}",
                provider="fake",
                retryable=False,
                raw_content=response_content[:500],
            ) from parse_exc

        if not isinstance(parsed_data, dict):
            raise LLMCallError(
                message=f"Fixture response is not a JSON object for {output_schema.__name__}",
                provider="fake",
                retryable=False,
                raw_content=response_content[:500],
            )

        try:
            return output_schema(**parsed_data)
        except Exception as validation_exc:
            raise LLMCallError(
                message=f"Failed to validate fixture for {output_schema.__name__}: {validation_exc}",
                provider="fake",
                retryable=False,
                raw_content=response_content[:500],
            ) from validation_exc

    def _log_event(
        self,
        event_type: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Helper to log telemetry events if a logger port is available."""
        if self._telemetry is not None and hasattr(self._telemetry, "log"):
            self._telemetry.log(message=message, level=level, event_type=event_type, **kwargs)
