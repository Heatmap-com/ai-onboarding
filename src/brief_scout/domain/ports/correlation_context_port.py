"""Correlation context port — contract for correlation ID management.

A narrow port for components that need to get or set the active correlation ID.
"""

from __future__ import annotations

from typing import Protocol


class CorrelationContext(Protocol):
    """Minimal port for correlation ID lifecycle."""

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
