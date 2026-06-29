"""Local File Telemetry Adapter — structured JSON logs to local files.

Composes smaller collaborators:
  - JsonlWriter for daily JSON Lines file I/O.
  - SpanStore for in-memory span tracking.

Implements the narrow telemetry ports (LoggerPort, EventRecorder,
SpanContext, CorrelationContext) as well as the composite TelemetryPort.
"""

from __future__ import annotations

import asyncio
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from brief_scout.domain.ports.telemetry_port import (
    LogLevel,
    TelemetryEvent,
)

if TYPE_CHECKING:
    from pathlib import Path
from brief_scout.infrastructure.telemetry.jsonl_writer import JsonlWriter
from brief_scout.infrastructure.telemetry.span_store import SpanStore

# Context variable for correlation ID tracking across async boundaries
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class LocalFileTelemetryAdapter:
    """Writes structured JSON logs to local files.

    One log file per day. Correlation IDs are tracked via contextvars
    for seamless propagation across async task boundaries.

    Log writes are performed asynchronously so that sync callers (e.g.
    ``LoggerPort`` implementations) do not block the event loop. When an
    event loop is available, writes are scheduled as background tasks and
    can be awaited via :meth:`flush`.

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
        log_dir: str | Path = "./logs",
        log_level: str = "INFO",
        writer: JsonlWriter | None = None,
        span_store: SpanStore | None = None,
    ) -> None:
        """Initialize the local file telemetry adapter.

        Args:
            log_dir: Directory path for log files.
            log_level: Minimum level to log.
            writer: Optional JsonlWriter instance.
            span_store: Optional SpanStore instance.
        """
        self._writer = writer or JsonlWriter(log_dir)
        self._min_level = LogLevel(log_level.upper())
        self._span_store = span_store or SpanStore()
        self._pending: set[asyncio.Task[Any]] = set()

    def _write(self, entry: dict[str, Any]) -> None:
        """Schedule an async write, falling back to sync when no loop exists."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Synchronous fallback for contexts without an event loop.
            import asyncio as _asyncio

            _asyncio.run(self._writer.write(entry))
            return

        task = loop.create_task(self._writer.write(entry))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def flush(self) -> None:
        """Await any pending background log writes."""
        if not self._pending:
            return
        pending = list(self._pending)
        self._pending.clear()
        await asyncio.gather(*pending, return_exceptions=True)

    def log(
        self,
        message: str,
        level: LogLevel | str = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Write a structured JSON log entry.

        Args:
            message: Human-readable log message.
            level: Severity level of the message (LogLevel preferred).
            **kwargs: Additional structured data to include.
        """
        level_enum = LogLevel(level.upper()) if isinstance(level, str) else level
        if self._LEVEL_ORDER[level_enum] < self._LEVEL_ORDER[self._min_level]:
            return

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level_enum.value,
            "message": message,
            "correlation_id": self.get_correlation_id(),
            "data": kwargs,
        }

        self._write(entry)

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a structured telemetry event."""
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

        self._write(entry)

    def start_span(
        self,
        name: str,
        correlation_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Start a tracing span.

        This method does NOT mutate the active correlation ID. Callers must
        explicitly use set_correlation_id if they want to change context.

        Args:
            name: Descriptive name for the span.
            correlation_id: Optional correlation ID stored with the span.
            **kwargs: Additional span attributes.

        Returns:
            A unique span identifier (UUID).
        """
        span_id = str(uuid.uuid4())
        cid = correlation_id or self.get_correlation_id()

        span_data = {
            "span_id": span_id,
            "name": name,
            "correlation_id": cid,
            "start_time": datetime.now(UTC).isoformat(),
            "attributes": kwargs,
        }

        self._span_store.add(span_id, span_data)

        self.log(
            message=f"Span started: {name}",
            level=LogLevel.DEBUG,
            span_id=span_id,
            **kwargs,
        )

        return span_id

    def end_span(self, span_id: str, **kwargs: Any) -> None:
        """End a tracing span and log its completion.

        Ending an unknown span_id is a no-op after logging a warning.

        Args:
            span_id: The span identifier returned by start_span.
            **kwargs: Additional data to include at span end.
        """
        span_data = self._span_store.remove(span_id)

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
        """Get the current correlation ID from context."""
        return _correlation_id_var.get("")

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID in the current context."""
        _correlation_id_var.set(correlation_id)

    # Backward-compatible accessors for existing tests
    @property
    def _log_dir(self) -> Path:
        """Return the log directory (deprecated, use writer)."""
        return self._writer._log_dir

    @property
    def _spans(self) -> dict[str, dict[str, Any]]:
        """Return the span store contents (deprecated, use span_store)."""
        return dict(self._span_store._spans)
