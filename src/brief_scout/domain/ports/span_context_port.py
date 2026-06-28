"""Span context port — contract for distributed tracing spans.

A narrow port for components that need to start and end tracing spans.
"""

from __future__ import annotations

from typing import Any, Protocol


class SpanContext(Protocol):
    """Minimal port for tracing span lifecycle."""

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
