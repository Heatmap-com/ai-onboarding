"""Local File Telemetry Adapter — structured JSON logs to local files.

Writes structured log entries as JSON Lines (JSONL) to daily log files.
Uses Python contextvars for correlation ID tracking across async boundaries.

Log file naming convention:
    ``{log_dir}/brief_scout_YYYY-MM-DD.jsonl``

Each line is a JSON object with timestamp, level, message, correlation_id,
and arbitrary structured data.

Example log entry::

    {
        "timestamp": "2026-01-15T09:30:00.123456",
        "level": "INFO",
        "message": "Intake completeness check completed",
        "correlation_id": "abc-123-def",
        "data": {"is_complete": true, "confidence": 0.85}
    }
"""

from __future__ import annotations

import json
import threading
import uuid
from contextvars import ContextVar
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from brief_scout.domain.ports.telemetry_port import (
    LogLevel,
    TelemetryEvent,
    TelemetryPort,
)

# Context variable for correlation ID tracking across async boundaries
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class LocalFileTelemetryAdapter(TelemetryPort):
    """Writes structured JSON logs to local files.

    One log file per day. Correlation IDs are tracked via contextvars
    for seamless propagation across async task boundaries.

    Attributes:
        log_dir: Directory where log files are written.
        log_level: Minimum log level to record.
    """

    _LEVEL_ORDER: dict[LogLevel, int] = {
        LogLevel.DEBUG: 0,
        LogLevel.INFO: 1,
        LogLevel.WARNING: 2,
        LogLevel.ERROR: 3,
        LogLevel.CRITICAL: 4,
    }

    def __init__(
        self,
        log_dir: str = "./logs",
        log_level: str = "INFO",
    ) -> None:
        """Initialize the local file telemetry adapter.

        Creates the log directory if it doesn't exist.

        Args:
            log_dir: Directory path for log files.
            log_level: Minimum level to log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._min_level = LogLevel(log_level.upper())
        self._spans: dict[str, dict[str, Any]] = {}
        self._spans_lock = threading.Lock()

    def log(
        self,
        message: str,
        level: LogLevel | str = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Write a structured JSON log entry.

        Args:
            message: Human-readable log message.
            level: Severity level of the message.
            **kwargs: Additional structured data to include.
        """
        level_enum = LogLevel(level.upper()) if isinstance(level, str) else level
        if self._LEVEL_ORDER[level_enum] < self._LEVEL_ORDER[self._min_level]:
            return

        level_str = level_enum.value
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level_str,
            "message": message,
            "correlation_id": self.get_correlation_id(),
            "data": kwargs,
        }

        self._write_entry(entry)

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a structured telemetry event.

        Events are written as JSON log entries with the event data
        nested under the ``data`` key.

        Args:
            event: The TelemetryEvent to record.
        """
        if self._LEVEL_ORDER.get(event.level, 0) < self._LEVEL_ORDER[self._min_level]:
            return

        entry = {
            "timestamp": event.timestamp.isoformat(),
            "level": event.level.value,
            "message": f"Telemetry event: {event.event_type}",
            "correlation_id": event.correlation_id or self.get_correlation_id(),
            "data": {
                "event_type": event.event_type,
                **event.data,
            },
        }

        self._write_entry(entry)

    def start_span(
        self,
        name: str,
        correlation_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Start a tracing span.

        Spans are stored in memory and logged at completion.

        Args:
            name: Descriptive name for the span.
            correlation_id: Optional correlation ID for the trace.
            **kwargs: Additional span attributes.

        Returns:
            A unique span identifier (UUID).
        """
        span_id = str(uuid.uuid4())
        cid = correlation_id or self.get_correlation_id()

        if cid:
            self.set_correlation_id(cid)

        span_data = {
            "span_id": span_id,
            "name": name,
            "correlation_id": cid,
            "start_time": datetime.now(UTC).isoformat(),
            "attributes": kwargs,
        }

        with self._spans_lock:
            self._spans[span_id] = span_data

        # Log span start
        self.log(
            message=f"Span started: {name}",
            level=LogLevel.DEBUG,
            span_id=span_id,
            **kwargs,
        )

        return span_id

    def end_span(self, span_id: str, **kwargs: Any) -> None:
        """End a tracing span and log its completion.

        Args:
            span_id: The span identifier returned by start_span.
            **kwargs: Additional data to include at span end.
        """
        with self._spans_lock:
            span_data = self._spans.pop(span_id, None)

        if span_data is None:
            self.log(
                message=f"Span not found for ending: {span_id}",
                level=LogLevel.WARNING,
            )
            return

        start_time = datetime.fromisoformat(span_data["start_time"])
        end_time = datetime.now(UTC)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        self.log(
            message=f"Span completed: {span_data['name']}",
            level=LogLevel.DEBUG,
            span_id=span_id,
            duration_ms=round(duration_ms, 2),
            correlation_id=span_data.get("correlation_id", ""),
            **{**(span_data.get("attributes") or {}), **kwargs},
        )

    def get_correlation_id(self) -> str:
        """Get the current correlation ID from context.

        Returns:
            The active correlation ID or empty string if none is set.
        """
        return _correlation_id_var.get("")

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID in the current context.

        Uses a contextvar so the ID propagates correctly across
        async task boundaries.

        Args:
            correlation_id: The correlation ID to set.
        """
        _correlation_id_var.set(correlation_id)

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a log entry to the current day's log file.

        Args:
            entry: The structured log entry dictionary.
        """
        log_file = self._log_dir / f"brief_scout_{date.today().isoformat()}.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as exc:
            # Fallback to stderr if file write fails
            import sys

            print(
                f"Failed to write log entry: {exc}",
                file=sys.stderr,
            )
