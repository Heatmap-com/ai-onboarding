"""Storage Port — composite contract for brief and session persistence.

This module now composes the narrow storage ports:
  - SessionStoragePort
  - BriefStoragePort
  - SessionLister

Adapters implementing BriefStoragePort (the composite) must satisfy all
three narrow contracts. Depend on the narrow ports in application/domain
code and use the composite only for composition-root wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief
    from brief_scout.domain.models.intake import ChatSession


class BriefStoragePort(Protocol):
    """Composite port for brief and session persistence.

    Implements SessionStoragePort + BriefStoragePort + SessionLister.
    """

    async def save_session(self, session: ChatSession) -> None:
        """Save a chat session."""
        ...

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a chat session by ID."""
        ...

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Save a generated brief associated with a session."""
        ...

    async def get_brief(self, session_id: str) -> Brief | None:
        """Retrieve a brief by its associated session ID."""
        ...

    async def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """List recent sessions ordered by creation time.

        Args:
            limit: Maximum number of sessions to return (default 100).

        Returns:
            A list of ChatSession objects, newest first.
        """
        ...
