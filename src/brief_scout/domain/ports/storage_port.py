"""Storage port — narrow read/write contracts for brief storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from brief_scout.domain.ports.session_storage_port import SessionReader, SessionWriter

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief


class BriefReader(Protocol):
    """Narrow port for loading briefs."""

    async def get_brief(self, session_id: str) -> Brief | None:
        """Return the brief if it exists, otherwise None."""
        ...


class BriefWriter(Protocol):
    """Narrow port for saving briefs."""

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Persist the brief."""
        ...


class BriefStoragePort(BriefReader, BriefWriter, SessionReader, SessionWriter, Protocol):
    """Combined narrow port for brief and session persistence."""

    ...
