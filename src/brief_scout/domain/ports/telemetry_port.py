"""Telemetry Port — composite contract for logging, metrics, and tracing.

This module now composes the narrow telemetry ports:
  - LoggerPort
  - EventRecorder
  - SpanContext
  - CorrelationContext

Adapters implementing TelemetryPort must satisfy all four narrow contracts.
The composite remains convenient for composition-root wiring; application
and domain code should depend on the narrow ports instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class LogLevel(StrEnum):
    """Standard log levels for structured logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TelemetryEvent(BaseModel):
    """A structured telemetry event.

    Events represent discrete occurrences in the system lifecycle,
    such as LLM call starts/ends, research step completions, or errors.

    Attributes:
        event_type: Dot-notation event category (e.g., 'llm.call.start').
        correlation_id: Trace/correlation identifier for distributed tracking.
        timestamp: When the event occurred (UTC).
        data: Arbitrary event-specific payload data.
        level: Severity level of the event.
    """

    event_type: str = ""
    correlation_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)
    level: LogLevel = LogLevel.INFO


class TelemetryPort(Protocol):
    """Composite port for logging, metrics, and tracing.

    Implementations may write to local files, stdout, OpenTelemetry
    collectors, or any other observability backend.

    This composite extends the narrow telemetry ports. It is intended for
    composition-root wiring only; depend on LoggerPort, EventRecorder,
    SpanContext, or CorrelationContext in application/domain code.
    """

    def log(
        self,
        message: str,
        level: LogLevel | str = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Log a structured message.

        The composite port accepts both ``LogLevel`` and plain strings for
        backward compatibility with legacy call sites. New code should pass
        ``LogLevel`` values.
        """
        ...

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a structured telemetry event."""
        ...

    def start_span(
        self,
        name: str,
        correlation_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Start a tracing span."""
        ...

    def end_span(self, span_id: str, **kwargs: Any) -> None:
        """End a tracing span.

        The contract is forgiving: ending an unknown span_id is a no-op
        (implementations may log a warning but must not raise).
        """
        ...

    def get_correlation_id(self) -> str:
        """Get the current correlation ID from context."""
        ...

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID in the current context."""
        ...
