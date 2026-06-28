"""Fake LLM Adapter — deterministic, fixture-based LLM responses.

This is the PRIMARY LLM adapter for the Brief Scout MVP. It simulates
LLM responses by loading JSON fixture files and matching them against
prompt content using keyword scoring. Zero network calls, zero cost,
100% deterministic.

Fixture files follow this structure::

    {
        "_meta": {
            "description": "Human-readable description",
            "match_keywords": ["brand_name", "task_type", "topic"],
            "latency_ms": 50
        },
        "response": { ... }
    }

The adapter:
1. Loads all JSON fixtures recursively from the fixture directory
2. Builds a keyword index from each fixture's ``_meta.match_keywords``
3. Matches incoming prompts by scoring keyword overlap against ``prompt.user``
4. Returns the best-matching fixture's response content
5. Falls back to a default fixture when no keywords match
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from brief_scout.domain.errors import LLMCallError
from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.domain.ports.telemetry_port import LogLevel, TelemetryEvent, TelemetryPort

T = TypeVar("T", bound=BaseModel)


class FakeLLMAdapter:
    """Deterministic LLM adapter that returns fixture-based responses.

    Loads JSON fixture files from a directory structure. Uses keyword
    scoring on the prompt content to select the appropriate fixture.

    Attributes:
        fixture_dir: Path to the fixtures directory.
        call_log: Record of all calls for test verification.
        latency_ms: Simulated latency in milliseconds.
    """

    def __init__(
        self,
        fixture_dir: str = "tests/fixtures/llm_responses",
        default_fixture: str = "default",
        latency_ms: float = 50.0,
        telemetry: TelemetryPort | None = None,
        demo_journey_path: str | None = None,
    ) -> None:
        """Initialize the Fake LLM Adapter.

        Args:
            fixture_dir: Directory containing JSON fixture files.
                         Loaded recursively — subdirectories are scanned.
            default_fixture: Name of the default fixture to use when
                             no keywords match.
            latency_ms: Default simulated latency in milliseconds.
            telemetry: Optional telemetry port for logging events.
            demo_journey_path: Optional YAML file with cumulative demo turn data.
                               When configured, ``demo_turn`` config selects a turn.
        """
        self._fixture_dir = Path(fixture_dir)
        self._default_fixture_name = default_fixture
        self._default_latency_ms = latency_ms
        self._telemetry = telemetry
        self._demo_journey_path = Path(demo_journey_path) if demo_journey_path else None
        self._fixtures: dict[str, dict[str, Any]] = {}
        self._keyword_index: list[dict[str, Any]] = []
        self._call_log: list[dict[str, Any]] = []
        self._demo_turns: list[dict[str, Any]] = []

        self._load_fixtures()
        self._load_demo_journey()

    def _load_fixtures(self) -> None:
        """Load all JSON fixture files from the fixture directory.

        Scans the directory recursively, loading every ``.json`` file.
        Builds the keyword index from each fixture's ``_meta.match_keywords``.

        If the fixture directory doesn't exist, only the default fixture
        will be available (returns empty responses).
        """
        if not self._fixture_dir.exists():
            self._log_event(
                "llm.fake.fixture_dir_missing",
                f"Fixture directory not found: {self._fixture_dir}",
            )
            return

        for json_file in self._fixture_dir.rglob("*.json"):
            try:
                fixture_data = json.loads(json_file.read_text())
                # Use relative path from fixture_dir as key to avoid collisions
                # e.g., "brand_audit/nike" instead of just "nike"
                rel_path = json_file.relative_to(self._fixture_dir)
                fixture_name = str(rel_path.with_suffix(""))
                self._fixtures[fixture_name] = fixture_data

                meta = fixture_data.get("_meta", {})
                keywords = meta.get("match_keywords", [])
                latency = meta.get("latency_ms", self._default_latency_ms)

                self._keyword_index.append(
                    {
                        "name": fixture_name,
                        "keywords": [kw.lower() for kw in keywords],
                        "latency_ms": latency,
                    }
                )

            except (json.JSONDecodeError, OSError) as exc:
                self._log_event(
                    "llm.fake.fixture_load_error",
                    f"Failed to load fixture {json_file}: {exc}",
                    level=LogLevel.WARNING,
                )

    def _load_demo_journey(self) -> None:
        """Load cumulative demo turn data from the configured YAML file."""
        if self._demo_journey_path is None or not self._demo_journey_path.exists():
            return
        try:
            raw = yaml.safe_load(self._demo_journey_path.read_text(encoding="utf-8"))
            turns = raw.get("turns", []) if isinstance(raw, dict) else []
            self._demo_turns = [t for t in turns if isinstance(t, dict)]
            self._log_event(
                "llm.fake.demo_journey_loaded",
                f"Loaded {len(self._demo_turns)} demo turns",
            )
        except (yaml.YAMLError, OSError) as exc:
            self._log_event(
                "llm.fake.demo_journey_load_error",
                f"Failed to load demo journey {self._demo_journey_path}: {exc}",
                level=LogLevel.WARNING,
            )

    def _demo_turn_fixture(
        self,
        turn_number: int,
    ) -> tuple[str, dict[str, Any], float] | None:
        """Build a fixture dict from the demo journey for a given turn.

        Args:
            turn_number: One-based turn index.

        Returns:
            A fixture tuple if the turn exists, otherwise None.
        """
        if not self._demo_turns or turn_number < 1 or turn_number > len(self._demo_turns):
            return None
        fixture_name = f"demo_turn_{turn_number}"
        fixture_data = {
            "_meta": {
                "description": f"Demo turn {turn_number}",
                "match_keywords": [],
                "latency_ms": self._default_latency_ms,
            },
            "response": self._demo_turns[turn_number - 1],
        }
        return fixture_name, fixture_data, float(self._default_latency_ms)

    def _match_fixture(
        self,
        prompt: Prompt,
        override_fixture: str | None = None,
        demo_turn: int | None = None,
    ) -> tuple[str, dict[str, Any], float]:
        """Pattern-match prompt content to find the best fixture.

        Matching strategy (in order):
        1. Demo journey turn override
        2. Explicit fixture name override in config
        3. Keyword matching on ``prompt.user`` content
        4. Default to ``_default_fixture_name``

        Args:
            prompt: The standardized prompt to match against.
            override_fixture: Explicit fixture name from config.
            demo_turn: Optional one-based demo turn number.

        Returns:
            Tuple of (fixture_name, fixture_data, latency_ms).
        """
        # Strategy 1: Demo journey turn
        if demo_turn is not None:
            demo_result = self._demo_turn_fixture(demo_turn)
            if demo_result is not None:
                return demo_result

        # Strategy 2: Explicit fixture name override
        if override_fixture:
            if override_fixture.startswith("demo_turn_"):
                turn_str = override_fixture.replace("demo_turn_", "")
                if turn_str.isdigit():
                    demo_result = self._demo_turn_fixture(int(turn_str))
                    if demo_result is not None:
                        return demo_result
            # Try exact match first, then fallback to stem name match
            if override_fixture in self._fixtures:
                meta = self._fixtures[override_fixture].get("_meta", {})
                latency = meta.get("latency_ms", self._default_latency_ms)
                return override_fixture, self._fixtures[override_fixture], float(latency)
            # Try matching by stem (last path component)
            for fixture_name, fixture_data in self._fixtures.items():
                if (
                    fixture_name.endswith(f"/{override_fixture}")
                    or fixture_name == override_fixture
                ):
                    meta = fixture_data.get("_meta", {})
                    latency = meta.get("latency_ms", self._default_latency_ms)
                    return fixture_name, fixture_data, float(latency)

        # Strategy 3: Keyword scoring on prompt.user
        user_text = prompt.user.lower() if prompt.user else ""

        best_match: str = self._default_fixture_name
        best_score: int = -1
        best_latency: float = self._default_latency_ms

        for entry in self._keyword_index:
            score = sum(1 for kw in entry["keywords"] if kw in user_text)
            if score > best_score:
                best_score = score
                best_match = entry["name"]
                best_latency = entry["latency_ms"]

        # Strategy 4: Default fallback when no keywords match
        if best_score <= 0:
            if best_match in self._fixtures:
                return best_match, self._fixtures[best_match], best_latency
            # Create a minimal default fixture on the fly
            return best_match, {"response": ""}, self._default_latency_ms

        return best_match, self._fixtures[best_match], best_latency

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Return a fixture-based response.

        1. Logs call start event
        2. Simulates latency via ``asyncio.sleep``
        3. Pattern-matches prompt against fixture index
        4. Loads matching fixture JSON
        5. Records call in call_log
        6. Returns LLMResponse with fixture content

        Args:
            prompt: The standardized prompt.
            config: Optional overrides (e.g., latency_ms, fixture_name).

        Returns:
            An LLMResponse with fixture content and metadata.

        Raises:
            LLMCallError: If the fixture response cannot be serialized.
        """
        merged_config = config or {}
        override_latency: float | None = merged_config.get("latency_ms")
        override_fixture: str | None = merged_config.get("fixture_name")
        demo_turn: int | None = merged_config.get("demo_turn")

        fixture_name, fixture_data, matched_latency = self._match_fixture(
            prompt,
            override_fixture=override_fixture,
            demo_turn=demo_turn,
        )
        latency_ms = override_latency if override_latency is not None else matched_latency

        # Simulate latency
        await asyncio.sleep(latency_ms / 1000.0)

        # Extract response content
        response_content = fixture_data.get("response", "")
        if isinstance(response_content, dict):
            response_content = json.dumps(response_content)
        elif not isinstance(response_content, str):
            response_content = str(response_content)

        # Build response
        response = LLMResponse(
            content=response_content,
            model_used="fake",
            provider="fake",
            tokens_used=len(response_content.split()),
            latency_ms=latency_ms,
            finish_reason="stop",
            metadata={
                "fixture_name": fixture_name,
                "fixture_dir": str(self._fixture_dir),
            },
        )

        # Record in call log
        call_record = {
            "fixture_name": fixture_name,
            "prompt_user": prompt.user[:500],
            "prompt_system": prompt.system[:500],
            "response_content": response_content[:1000],
            "latency_ms": latency_ms,
            "timestamp": asyncio.get_event_loop().time(),
        }
        self._call_log.append(call_record)

        # Telemetry
        if self._telemetry:
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

                Calls ``complete()`` to get the fixture response, then attempts
        to parse the content as JSON and validate it against the provided
                Pydantic model. If parsing fails, returns a default instance.

                Args:
                    prompt: The standardized prompt.
                    output_schema: A Pydantic model class to parse into.
                    config: Optional provider-specific configuration overrides.

                Returns:
                    An instance of output_schema populated from fixture data.

                Raises:
                    LLMCallError: If JSON parsing and default instantiation both fail.
        """
        response = await self.complete(prompt, config)

        raw_content = response.content.strip()
        if not raw_content:
            return output_schema()

        # Try to parse as JSON
        try:
            # Handle markdown code fences
            if raw_content.startswith("```"):
                lines = raw_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()

            parsed_data = json.loads(raw_content)

            if isinstance(parsed_data, dict):
                return output_schema(**parsed_data)

            # If parsed JSON is not a dict, wrap it
            return output_schema()

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self._log_event(
                "llm.fake.parse_error",
                f"Failed to parse fixture JSON for {output_schema.__name__}: {exc}",
                level=LogLevel.WARNING,
                raw_content_preview=raw_content[:200],
            )
            # Return default instance
            try:
                return output_schema()
            except Exception as default_exc:
                raise LLMCallError(
                    message=f"Failed to create default {output_schema.__name__}: {default_exc}",
                    provider="fake",
                    retryable=False,
                ) from default_exc

    @property
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            The string ``"fake"``.
        """
        return "fake"

    def get_call_log(self) -> list[dict[str, Any]]:
        """Return all recorded calls for test verification.

        Returns:
            A list of call record dictionaries, each containing the
            fixture name, prompt snippet, response snippet, and latency.
        """
        return list(self._call_log)

    def clear_call_log(self) -> None:
        """Clear the call log between tests.

        Removes all recorded calls, resetting the adapter to a clean state.
        """
        self._call_log.clear()

    def _log_event(
        self,
        event_type: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Helper to log telemetry events if a telemetry port is available.

        Args:
            event_type: Dot-notation event type string.
            message: Human-readable message.
            level: Log severity level.
            **kwargs: Additional event data.
        """
        if self._telemetry:
            self._telemetry.log(message=message, level=level, event_type=event_type, **kwargs)
