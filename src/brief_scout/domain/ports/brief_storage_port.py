"""Brief storage port — contract for brief persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief


class BriefStoragePort(Protocol):
    """Port for generated brief persistence."""

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
