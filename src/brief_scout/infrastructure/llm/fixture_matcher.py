"""Fixture matcher — prompt-to-fixture matching strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt
    from brief_scout.infrastructure.llm.demo_journey_player import DemoJourneyPlayer
    from brief_scout.infrastructure.llm.fixture_repository import FixtureRepository


class FixtureMatcher:
    """Matches prompts to fixtures using multiple strategies."""

    def __init__(
        self,
        repository: FixtureRepository,
        demo_player: DemoJourneyPlayer,
    ) -> None:
        """Initialize the matcher.

        Args:
            repository: Loaded fixture repository.
            demo_player: Demo journey player for demo turn fixtures.
        """
        self._repository = repository
        self._demo_player = demo_player

    def match(
        self,
        prompt: Prompt,
        override_fixture: str | None = None,
        demo_turn: int | None = None,
    ) -> tuple[str, dict[str, Any], float]:
        """Pattern-match prompt content to find the best fixture.

        Strategy order:
        1. Demo journey turn override
        2. Explicit fixture name override
        3. Keyword matching on prompt.user
        4. Default fixture

        Args:
            prompt: The standardized prompt to match against.
            override_fixture: Explicit fixture name from config.
            demo_turn: Optional one-based demo turn number.

        Returns:
            Tuple of (fixture_name, fixture_data, latency_ms).
        """
        # Strategy 1: Demo journey turn
        if demo_turn is not None:
            demo_result = self._demo_player.build_fixture(demo_turn)
            if demo_result is not None:
                return demo_result

        # Strategy 2: Explicit fixture name override
        if override_fixture:
            if override_fixture.startswith("demo_turn_"):
                turn_str = override_fixture.replace("demo_turn_", "")
                if turn_str.isdigit():
                    demo_result = self._demo_player.build_fixture(int(turn_str))
                    if demo_result is not None:
                        return demo_result
            fixtures = self._repository.fixtures
            if override_fixture in fixtures:
                meta = fixtures[override_fixture].get("_meta", {})
                latency = meta.get("latency_ms", self._repository.default_latency_ms)
                return override_fixture, fixtures[override_fixture], float(latency)
            for fixture_name, fixture_data in fixtures.items():
                if (
                    fixture_name.endswith(f"/{override_fixture}")
                    or fixture_name == override_fixture
                ):
                    meta = fixture_data.get("_meta", {})
                    latency = meta.get("latency_ms", self._repository.default_latency_ms)
                    return fixture_name, fixture_data, float(latency)

        # Strategy 3: Keyword scoring on prompt.user
        user_text = prompt.user.lower() if prompt.user else ""
        best_match = self._repository.default_fixture_name
        best_score = -1
        best_latency = self._repository.default_latency_ms

        for entry in self._repository.keyword_index:
            score = sum(1 for kw in entry["keywords"] if kw in user_text)
            if score > best_score:
                best_score = score
                best_match = entry["name"]
                best_latency = entry["latency_ms"]

        # Strategy 4: Default fallback when no keywords match
        if best_score <= 0:
            return self._repository.create_default()

        return best_match, self._repository.fixtures[best_match], best_latency
