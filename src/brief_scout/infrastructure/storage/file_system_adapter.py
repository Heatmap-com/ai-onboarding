"""File System Storage Adapter — persists sessions and briefs as JSON files.

Stores ChatSession and Brief objects as individual JSON files on disk.
Each entity type has its own subdirectory. Files are named with the
session ID for easy lookup.

Directory structure::

    {data_dir}/
        sessions/
            {session_id_1}.json
            {session_id_2}.json
        briefs/
            {session_id_1}.json
            {session_id_2}.json

This adapter provides persistence across restarts without requiring
an external database, making it suitable for single-instance deployments.
"""

from __future__ import annotations

from pathlib import Path

from brief_scout.domain.models.brief import Brief
from brief_scout.domain.models.intake import ChatSession
from brief_scout.domain.ports.storage_port import BriefStoragePort


class FileSystemStorageAdapter(BriefStoragePort):
    """Persists sessions and briefs as JSON files on disk.

    One directory per entity type. Files named ``{session_id}.json``.
    Creates directories automatically on initialization.

    Attributes:
        _data_dir: Root directory for all data storage.
        _sessions_dir: Subdirectory for session JSON files.
        _briefs_dir: Subdirectory for brief JSON files.
    """

    def __init__(self, data_dir: str = "./data") -> None:
        """Initialize the file system storage adapter.

        Creates the directory structure if it doesn't already exist.

        Args:
            data_dir: Root directory for data files.
        """
        self._data_dir = Path(data_dir)
        self._sessions_dir = self._data_dir / "sessions"
        self._briefs_dir = self._data_dir / "briefs"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._briefs_dir.mkdir(parents=True, exist_ok=True)

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session as a JSON file.

        Args:
            session: The ChatSession to persist.
        """
        filepath = self._sessions_dir / f"{session.session_id}.json"
        filepath.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            The ChatSession if found, None otherwise.
        """
        filepath = self._sessions_dir / f"{session_id}.json"
        if not filepath.exists():
            return None
        return ChatSession.model_validate_json(filepath.read_text(encoding="utf-8"))

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session.

        Args:
            session_id: The session identifier to associate the brief with.
            brief: The Brief to persist.
        """
        filepath = self._briefs_dir / f"{session_id}.json"
        filepath.write_text(brief.model_dump_json(indent=2), encoding="utf-8")

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID.

        Args:
            session_id: The session identifier the brief is associated with.

        Returns:
            The Brief if found, None otherwise.
        """
        filepath = self._briefs_dir / f"{session_id}.json"
        if not filepath.exists():
            return None
        return Brief.model_validate_json(filepath.read_text(encoding="utf-8"))

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time (newest first).

        Reads all session files and sorts by the session's created_at field.

        Args:
            limit: Maximum number of sessions to return (default 100).

        Returns:
            A list of ChatSession objects, newest first.
        """
        sessions: list[ChatSession] = []

        if not self._sessions_dir.exists():
            return sessions

        for filepath in sorted(self._sessions_dir.glob("*.json")):
            try:
                session = ChatSession.model_validate_json(filepath.read_text(encoding="utf-8"))
                sessions.append(session)
            except Exception:
                # Skip corrupted files
                continue

        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]
