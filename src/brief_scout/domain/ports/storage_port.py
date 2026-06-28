"""Storage Port — contract for brief and session persistence.

Adapters implementing this Protocol handle the mechanics of persisting
chat sessions and generated briefs. The domain layer depends only on
this interface, allowing transparent swapping between in-memory, file
system, and database storage backends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief
    from brief_scout.domain.models.intake import ChatSession


class BriefStoragePort(Protocol):
    """Port for brief and session persistence.

    Implementations may store data in memory, on the file system,
    or in external databases. All operations are async to support
    non-blocking I/O.
    """

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

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session.

        Args:
            session_id: The session identifier to associate the brief with.
            brief: The Brief to persist.
        """
        ...

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID.

        Args:
            session_id: The session identifier the brief is associated with.

        Returns:
            The Brief if found, None otherwise.
        """
        ...

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time.

        Args:
            limit: Maximum number of sessions to return (default 100).

        Returns:
            A list of ChatSession objects, newest first.
        """
        ...
