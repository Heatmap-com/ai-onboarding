"""Logger port — minimal structured logging contract.

A narrow port for components that only need to emit structured log messages.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from brief_scout.domain.ports.telemetry_port import LogLevel


@runtime_checkable
class LoggerPort(Protocol):
    """Minimal port for structured logging."""

    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Log a structured message.

        Args:
            message: The human-readable log message.
            level: Severity level (default INFO).
            **kwargs: Additional structured data to include.
        """
        ...
