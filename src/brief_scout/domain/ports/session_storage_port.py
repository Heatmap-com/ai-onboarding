"""Session storage port — contract for chat session persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatSession


class SessionStoragePort(Protocol):
    """Port for chat session persistence."""

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session.

        Args:
            session: The ChatSession to persist.
        """
        ...

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            The ChatSession if found, None otherwise.
        """
        ...
