"""Event recorder port — contract for recording structured telemetry events.

A narrow port for components that only need to emit discrete telemetry events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from brief_scout.domain.ports.telemetry_port import TelemetryEvent


@runtime_checkable
class EventRecorder(Protocol):
    """Minimal port for recording structured telemetry events."""

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a structured telemetry event.

        Args:
            event: The TelemetryEvent to record.
        """
        ...
