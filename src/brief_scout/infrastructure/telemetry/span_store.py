"""Span store — in-memory span tracking."""

from __future__ import annotations

import threading
from typing import Any


class SpanStore:
    """Stores in-memory tracing spans and reports unknown span endings."""

    def __init__(self) -> None:
        """Initialize the span store."""
        self._spans: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add(self, span_id: str, data: dict[str, Any]) -> None:
        """Add a span to the store.

        Args:
            span_id: Unique span identifier.
            data: Span data dictionary.
        """
        with self._lock:
            self._spans[span_id] = data

    def remove(self, span_id: str) -> dict[str, Any] | None:
        """Remove and return a span by ID.

        Args:
            span_id: Unique span identifier.

        Returns:
            The span data if found, None otherwise.
        """
        with self._lock:
            return self._spans.pop(span_id, None)

    def get(self, span_id: str) -> dict[str, Any] | None:
        """Return a span by ID without removing it.

        Args:
            span_id: Unique span identifier.

        Returns:
            The span data if found, None otherwise.
        """
        with self._lock:
            return self._spans.get(span_id)
