"""Session storage port — narrow read/write contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatSession


class SessionReader(Protocol):
    """Narrow port for loading chat sessions."""

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Return the session if it exists, otherwise None."""
        ...


class SessionWriter(Protocol):
    """Narrow port for saving chat sessions."""

    async def save_session(self, session: ChatSession) -> None:
        """Persist the chat session."""
        ...


class SessionStoragePort(SessionReader, SessionWriter, Protocol):
    """Combined narrow port for session persistence."""

    ...
