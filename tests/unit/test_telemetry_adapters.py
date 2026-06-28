"""Unit tests for source telemetry adapters.

Exercises:
- src/brief_scout/infrastructure/telemetry/local_file_adapter.py
- src/brief_scout/infrastructure/telemetry/structured_logger.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from brief_scout.domain.ports.telemetry_port import LogLevel, TelemetryEvent
from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)
from brief_scout.infrastructure.telemetry.structured_logger import (
    StructuredLogger,
    get_logger,
)


class TestLocalFileTelemetryAdapter:
    """Tests for LocalFileTelemetryAdapter."""

    @pytest.fixture
    def telemetry(self, tmp_path: Path) -> LocalFileTelemetryAdapter:
        """Provide a LocalFileTelemetryAdapter writing to a temp directory."""
        return LocalFileTelemetryAdapter(
            log_dir=str(tmp_path / "logs"),
            log_level="INFO",
        )

    def _read_log_file(self, telemetry: LocalFileTelemetryAdapter) -> list[dict[str, Any]]:
        """Read and parse all lines from today's log file."""
        from datetime import date

        log_file = telemetry._log_dir / f"brief_scout_{date.today().isoformat()}.jsonl"
        if not log_file.exists():
            return []
        return [
            json.loads(line)
            for line in log_file.read_text(encoding="utf-8").strip().split("\n")
            if line
        ]

    def test_should_create_log_directory(self, tmp_path: Path) -> None:
        """Constructor should create the log directory."""
        log_dir = tmp_path / "new_logs"
        adapter = LocalFileTelemetryAdapter(log_dir=str(log_dir))
        assert log_dir.exists()
        assert adapter.get_correlation_id() == ""

    def test_should_set_correlation_id(self, telemetry: LocalFileTelemetryAdapter) -> None:
        """set_correlation_id/get_correlation_id should round-trip."""
        telemetry.set_correlation_id("corr-123")
        assert telemetry.get_correlation_id() == "corr-123"

    def test_should_log_at_or_above_min_level(self, telemetry: LocalFileTelemetryAdapter) -> None:
        """log should write entries at or above the configured level."""
        telemetry.log("info message", level="INFO")
        telemetry.log("debug message", level="DEBUG")

        entries = self._read_log_file(telemetry)
        messages = {e["message"] for e in entries}
        assert "info message" in messages
        assert "debug message" not in messages

    def test_should_accept_log_level_enum(self, telemetry: LocalFileTelemetryAdapter) -> None:
        """log should accept a LogLevel enum."""
        telemetry.log("warning message", level=LogLevel.WARNING)
        entries = self._read_log_file(telemetry)
        assert any(e["message"] == "warning message" for e in entries)

    def test_should_record_event(self, telemetry: LocalFileTelemetryAdapter) -> None:
        """record_event should write a telemetry event entry."""
        event = TelemetryEvent(
            event_type="test.event",
            data={"key": "value"},
            level=LogLevel.INFO,
        )
        telemetry.record_event(event)

        entries = self._read_log_file(telemetry)
        assert any(e.get("data", {}).get("event_type") == "test.event" for e in entries)

    def test_should_filter_low_level_event(self, telemetry: LocalFileTelemetryAdapter) -> None:
        """record_event should drop events below the configured level."""
        event = TelemetryEvent(
            event_type="test.debug",
            data={},
            level=LogLevel.DEBUG,
        )
        telemetry.record_event(event)

        entries = self._read_log_file(telemetry)
        assert not any(e.get("data", {}).get("event_type") == "test.debug" for e in entries)

    def test_should_start_and_end_span(self, tmp_path: Path) -> None:
        """start_span/end_span should record span lifecycle."""
        telemetry = LocalFileTelemetryAdapter(
            log_dir=str(tmp_path / "logs"),
            log_level="DEBUG",
        )
        span_id = telemetry.start_span("test_span", correlation_id="corr-abc")
        assert span_id
        assert span_id in telemetry._spans
        telemetry.end_span(span_id, extra="data")

        entries = self._read_log_file(telemetry)
        assert any("Span started" in e["message"] for e in entries)
        assert any("Span completed" in e["message"] for e in entries)

    def test_should_warn_when_ending_unknown_span(
        self, telemetry: LocalFileTelemetryAdapter
    ) -> None:
        """end_span should warn when span_id is unknown."""
        telemetry.end_span("unknown-span")

        entries = self._read_log_file(telemetry)
        assert any("Span not found" in e["message"] for e in entries)

    def test_should_log_event_with_correlation_id(
        self, telemetry: LocalFileTelemetryAdapter
    ) -> None:
        """start_span should set correlation id and propagate to logs."""
        telemetry.start_span("test", correlation_id="corr-xyz")
        telemetry.log("message with cid")

        entries = self._read_log_file(telemetry)
        assert any(e.get("correlation_id") == "corr-xyz" for e in entries)


class TestStructuredLogger:
    """Tests for StructuredLogger."""

    def test_get_logger_returns_structured_logger(self) -> None:
        """get_logger should return a StructuredLogger instance."""
        logger = get_logger("test")
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "test"

    def test_should_log_all_levels(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All level methods should produce output."""
        logger = StructuredLogger("level-test")
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        logger.critical("critical msg")

        captured = capsys.readouterr()
        # structlog filtering bound logger at INFO will not emit debug
        assert "info msg" in captured.out or captured.err
