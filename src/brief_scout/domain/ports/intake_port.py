"""Intake port — narrow contract for intake interview orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatSession


class IntakePort(Protocol):
    """Narrow port for driving the intake interview."""

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
    ) -> Any:
        """Process user message and return the assistant reply and updated state."""
        ...
