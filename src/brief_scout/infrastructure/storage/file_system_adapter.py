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

import json
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from pydantic import ValidationError

from brief_scout.domain.models.brief import Brief
from brief_scout.domain.models.intake import ChatSession
from brief_scout.domain.ports.session_lister_port import SessionLister
from brief_scout.domain.ports.session_storage_port import SessionStoragePort
from brief_scout.domain.ports.storage_port import BriefStoragePort
from brief_scout.domain.ports.telemetry_port import LogLevel

if TYPE_CHECKING:
    from brief_scout.domain.ports.logger_port import LoggerPort


class FileSystemStorageAdapter(
    SessionStoragePort,
    BriefStoragePort,
    SessionLister,
):
    """Persists sessions and briefs as JSON files on disk."""

    def __init__(
        self,
        data_dir: str = "./data",
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize the file system storage adapter.

        Args:
            data_dir: Root directory for data files.
            logger: Optional logger for corrupted-file diagnostics.
        """
        self._data_dir = Path(data_dir)
        self._sessions_dir = self._data_dir / "sessions"
        self._briefs_dir = self._data_dir / "briefs"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._briefs_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session as a JSON file."""
        filepath = self._sessions_dir / f"{session.session_id}.json"
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(session.model_dump_json(indent=2))

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID.

        Returns:
            The ChatSession if found, None if missing or corrupted.
        """
        filepath = self._sessions_dir / f"{session_id}.json"
        if not filepath.exists():
            return None
        try:
            async with aiofiles.open(filepath, encoding="utf-8") as f:
                data = await f.read()
            return ChatSession.model_validate_json(data)
        except (ValidationError, json.JSONDecodeError, OSError):
            if self._logger is not None:
                self._logger.log(
                    message=f"Corrupted session file: {filepath}",
                    level=LogLevel.WARNING,
                    session_id=session_id,
                )
            return None

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session."""
        filepath = self._briefs_dir / f"{session_id}.json"
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(brief.model_dump_json(indent=2))

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID."""
        filepath = self._briefs_dir / f"{session_id}.json"
        if not filepath.exists():
            return None
        try:
            async with aiofiles.open(filepath, encoding="utf-8") as f:
                data = await f.read()
            return Brief.model_validate_json(data)
        except (ValidationError, json.JSONDecodeError, OSError):
            if self._logger is not None:
                self._logger.log(
                    message=f"Corrupted brief file: {filepath}",
                    level=LogLevel.WARNING,
                    session_id=session_id,
                )
            return None

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time (newest first).

        Corrupted files are logged and skipped.
        """
        sessions: list[ChatSession] = []

        if not self._sessions_dir.exists():
            return sessions

        for filepath in sorted(self._sessions_dir.glob("*.json")):
            try:
                async with aiofiles.open(filepath, encoding="utf-8") as f:
                    data = await f.read()
                session = ChatSession.model_validate_json(data)
                sessions.append(session)
            except (ValidationError, json.JSONDecodeError, OSError) as exc:
                if self._logger is not None:
                    self._logger.log(
                        message=f"Skipping corrupted session file: {filepath}",
                        level=LogLevel.WARNING,
                        error=str(exc),
                    )
                continue

        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]
