"""Research step registry port — contract for discovering research steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brief_scout.application.services.research_steps import ResearchStep


class ResearchStepRegistry(Protocol):
    """Provide the ordered sequence of research steps to execute."""

    @property
    def steps(self) -> Sequence[ResearchStep]:
        """Return all registered research steps."""
        ...
