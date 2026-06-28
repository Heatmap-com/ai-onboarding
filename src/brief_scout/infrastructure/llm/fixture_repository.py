"""Fixture repository — recursive fixture loading and keyword indexing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brief_scout.domain.ports.telemetry_port import LogLevel

if TYPE_CHECKING:
    from brief_scout.domain.ports.logger_port import LoggerPort


class FixtureRepository:
    """Loads JSON fixtures recursively and indexes them by keywords."""

    def __init__(
        self,
        fixture_dir: str | Path,
        default_fixture_name: str = "default",
        default_latency_ms: float = 50.0,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize the repository.

        Args:
            fixture_dir: Directory containing JSON fixture files.
            default_fixture_name: Name of the default fixture.
            default_latency_ms: Default simulated latency.
            logger: Optional logger for diagnostics.
        """
        self._fixture_dir = Path(fixture_dir)
        self._default_fixture_name = default_fixture_name
        self._default_latency_ms = default_latency_ms
        self._logger = logger
        self._fixtures: dict[str, dict[str, Any]] = {}
        self._keyword_index: list[dict[str, Any]] = []
        self._load_fixtures()

    @property
    def fixtures(self) -> dict[str, dict[str, Any]]:
        """Return the loaded fixtures."""
        return dict(self._fixtures)

    @property
    def keyword_index(self) -> list[dict[str, Any]]:
        """Return the keyword index."""
        return list(self._keyword_index)

    @property
    def default_fixture_name(self) -> str:
        """Return the default fixture name."""
        return self._default_fixture_name

    @property
    def default_latency_ms(self) -> float:
        """Return the default simulated latency."""
        return self._default_latency_ms

    @property
    def fixture_dir(self) -> Path:
        """Return the fixture directory path."""
        return self._fixture_dir

    def get(self, name: str) -> dict[str, Any] | None:
        """Get a fixture by exact name."""
        return self._fixtures.get(name)

    def create_default(self) -> tuple[str, dict[str, Any], float]:
        """Return a minimal default fixture tuple."""
        name = self._default_fixture_name
        if name in self._fixtures:
            data = self._fixtures[name]
            meta = data.get("_meta", {})
            latency = meta.get("latency_ms", self._default_latency_ms)
            return name, data, float(latency)
        return name, {"response": ""}, self._default_latency_ms

    def _load_fixtures(self) -> None:
        """Load all JSON fixture files from the fixture directory."""
        if not self._fixture_dir.exists():
            self._log_event(
                "llm.fake.fixture_dir_missing",
                f"Fixture directory not found: {self._fixture_dir}",
            )
            return

        for json_file in self._fixture_dir.rglob("*.json"):
            try:
                fixture_data = json.loads(json_file.read_text())
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
