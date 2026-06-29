"""Pipeline port — narrow contract for pipeline execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from brief_scout.application.services import PipelineEvent
    from brief_scout.domain.models.intake import ChatSession


class PipelinePort(Protocol):
    """Narrow port for executing the brief generation pipeline."""

    def run(
        self,
        session: ChatSession,
        user_message: str | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        """Execute the pipeline and yield progress events."""
        ...
