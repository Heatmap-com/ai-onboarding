"""Session lister port — contract for listing chat sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatSession


class SessionLister(Protocol):
    """Port for listing persisted chat sessions."""

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time.

        Args:
            limit: Maximum number of sessions to return (default 100).

        Returns:
            A list of ChatSession objects, newest first.
        """
        ...
