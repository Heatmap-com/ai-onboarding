"""Demo journey player — synthesizes fixtures from a demo-journey YAML file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from brief_scout.domain.ports.telemetry_port import LogLevel

if TYPE_CHECKING:
    from brief_scout.domain.ports.logger_port import LoggerPort


class DemoJourneyPlayer:
    """Loads cumulative demo turn data and builds fixtures for demo turns."""

    def __init__(
        self,
        demo_journey_path: str | Path | None,
        default_latency_ms: float = 50.0,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize the demo journey player.

        Args:
            demo_journey_path: Path to the demo journey YAML file.
            default_latency_ms: Default simulated latency for demo turns.
            logger: Optional logger for diagnostics.
        """
        self._demo_journey_path = Path(demo_journey_path) if demo_journey_path else None
        self._default_latency_ms = default_latency_ms
        self._logger = logger
        self._demo_turns: list[dict[str, Any]] = []
        self._load_demo_journey()

    def build_fixture(
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

    def _log_event(
        self,
        event_type: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Helper to log telemetry events if a logger port is available."""
        if self._logger is not None:
            self._logger.log(message=message, level=level, event_type=event_type, **kwargs)
