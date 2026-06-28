"""Structured logger — wrapper around structlog for type-safe logging.

Provides a convenience wrapper that bridges the TelemetryPort interface
with structlog's structured logging capabilities. This module is optional
— if structlog is not installed, logging falls back to the standard
library with JSON formatting.

Usage::

    from brief_scout.infrastructure.telemetry.structured_logger import get_logger
    logger = get_logger("brief_scout.research")
    logger.info("Research started", brand_name="Nike")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    import structlog

    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False

from brief_scout.domain.ports.telemetry_port import LogLevel


def _configure_structlog() -> None:
    """Configure structlog with JSON renderer and standard processors."""
    if not _STRUCTLOG_AVAILABLE:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ExtraAdder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class StructuredLogger:
    """Structured logger that wraps structlog or standard logging.

    Provides a unified interface for structured logging with support
    for key-value pairs, correlation IDs, and JSON output.

    Attributes:
        name: The logger name (typically the module path).
    """

    def __init__(self, name: str = "brief_scout") -> None:
        """Initialize the structured logger.

        Args:
            name: The logger name for identification.
        """
        self.name = name

        if _STRUCTLOG_AVAILABLE:
            _configure_structlog()
            self._logger = structlog.get_logger(name)
        else:
            self._logger = logging.getLogger(name)
            # Set up JSON formatting fallback
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter(
                    fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"name": "%(name)s", "message": "%(message)s"}'
                )
            )
            if not self._logger.handlers:
                self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a DEBUG level message.

        Args:
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an INFO level message.

        Args:
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a WARNING level message.

        Args:
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an ERROR level message.

        Args:
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a CRITICAL level message.

        Args:
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def _log(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        """Internal method to route log messages to the underlying logger.

        Args:
            level: The log level.
            message: The log message.
            **kwargs: Additional structured key-value pairs.
        """
        if _STRUCTLOG_AVAILABLE:
            method_name = level.value.lower()
            log_method = getattr(self._logger, method_name, self._logger.info)
            if kwargs:
                log_method(message, **kwargs)
            else:
                log_method(message)
        else:
            std_level = getattr(logging, level.value, logging.INFO)
            if kwargs:
                self._logger.log(std_level, "%s | %s", message, kwargs)
            else:
                self._logger.log(std_level, "%s", message)


def get_logger(name: str = "brief_scout") -> StructuredLogger:
    """Get a named structured logger.

    Factory function that returns a StructuredLogger instance.

    Args:
        name: The logger name (typically module path).

    Returns:
        A configured StructuredLogger instance.
    """
    return StructuredLogger(name)
