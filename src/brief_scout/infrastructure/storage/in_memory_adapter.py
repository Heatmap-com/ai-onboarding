"""In-Memory Storage Adapter — non-persistent storage for sessions and briefs.

Simple in-memory dictionaries for ChatSession and Brief objects.
NOT persistent across restarts. For MVP and testing only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.ports.session_lister_port import SessionLister
from brief_scout.domain.ports.session_storage_port import SessionStoragePort
from brief_scout.domain.ports.storage_port import BriefStoragePort

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief
    from brief_scout.domain.models.intake import ChatSession


class InMemoryStorageAdapter(
    SessionStoragePort,
    BriefStoragePort,
    SessionLister,
):
    """Simple in-memory storage for sessions and briefs."""

    def __init__(self) -> None:
        """Initialize the in-memory storage with empty dictionaries."""
        self._sessions: dict[str, ChatSession] = {}
        self._briefs: dict[str, Brief] = {}

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session."""
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID."""
        return self._sessions.get(session_id)

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session."""
        self._briefs[session_id] = brief

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID."""
        return self._briefs.get(session_id)

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time (newest first)."""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return sessions[:limit]
