"""In-Memory Storage Adapter — non-persistent storage for sessions and briefs.

Simple in-memory dictionaries for ChatSession and Brief objects.
NOT persistent across restarts. For MVP and testing only.

This adapter is useful for:
- Development and testing (no file I/O)
- Scenarios where persistence is not required
- Fast integration tests with clean state per run
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.ports.storage_port import BriefStoragePort

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief
    from brief_scout.domain.models.intake import ChatSession


class InMemoryStorageAdapter(BriefStoragePort):
    """Simple in-memory storage for sessions and briefs.

    Stores ChatSession and Brief objects in Python dictionaries.
    All data is lost when the process restarts.

    Attributes:
        _sessions: Dictionary mapping session_id to ChatSession.
        _briefs: Dictionary mapping session_id to Brief.
    """

    def __init__(self) -> None:
        """Initialize the in-memory storage with empty dictionaries."""
        self._sessions: dict[str, ChatSession] = {}
        self._briefs: dict[str, Brief] = {}

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session.

        Args:
            session: The ChatSession to persist in memory.
        """
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            The ChatSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session.

        Args:
            session_id: The session identifier to associate the brief with.
            brief: The Brief to persist in memory.
        """
        self._briefs[session_id] = brief

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID.

        Args:
            session_id: The session identifier the brief is associated with.

        Returns:
            The Brief if found, None otherwise.
        """
        return self._briefs.get(session_id)

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time (newest first).

        Args:
            limit: Maximum number of sessions to return (default 100).

        Returns:
            A list of ChatSession objects sorted by created_at descending.
        """
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return sessions[:limit]
