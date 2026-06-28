"""Telemetry Port — contract for logging, metrics, and tracing.

Adapters implementing this Protocol handle the mechanics of recording
observability data: structured logs, telemetry events, and distributed
tracing spans. The domain layer depends only on this interface.
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
    """Port for logging, metrics, and tracing.

    Implementations may write to local files, stdout, OpenTelemetry
    collectors, or any other observability backend.
    """

    def log(
        self,
        message: str,
        level: LogLevel | str = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Log a structured message.

        Args:
            message: The human-readable log message.
            level: Severity level (default INFO).
            **kwargs: Additional structured data to include.
        """
        ...

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a structured telemetry event.

        Args:
            event: The TelemetryEvent to record.
        """
        ...

    def start_span(
        self,
        name: str,
        correlation_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Start a tracing span.

        Args:
            name: Descriptive name for the span.
            correlation_id: Optional correlation ID for the trace.
            **kwargs: Additional span attributes.

        Returns:
            A unique span identifier.
        """
        ...

    def end_span(self, span_id: str, **kwargs: Any) -> None:
        """End a tracing span.

        Args:
            span_id: The span identifier returned by start_span.
            **kwargs: Additional data to include at span end.
        """
        ...

    def get_correlation_id(self) -> str:
        """Get the current correlation ID from context.

        Returns:
            The active correlation ID or empty string if none set.
        """
        ...

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID in the current context.

        Args:
            correlation_id: The correlation ID to set.
        """
        ...
