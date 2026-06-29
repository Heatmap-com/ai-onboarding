"""Storage port — narrow read/write contracts for brief storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from brief_scout.domain.ports.session_storage_port import SessionReader, SessionWriter

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief


@runtime_checkable
class BriefReader(Protocol):
    """Narrow port for loading briefs."""

    async def get_brief(self, session_id: str) -> Brief | None:
        """Return the brief if it exists, otherwise None."""
        ...


@runtime_checkable
class BriefWriter(Protocol):
    """Narrow port for saving briefs."""

    async def save_brief(self, session_id: str, brief: Brief) -> None:
        """Persist the brief."""
        ...


@runtime_checkable
class BriefStoragePort(BriefReader, BriefWriter, SessionReader, SessionWriter, Protocol):
    """Combined narrow port for brief and session persistence."""

    ...
