"""Port for creating a configured search/retrieval tool.

Keeps the composition root decoupled from concrete search implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import SearchConfig
    from brief_scout.domain.ports.research_tool_port import ResearchTool


class SearchToolFactory(Protocol):
    """Factory that creates a ``ResearchTool`` from search configuration."""

    def create(self, config: SearchConfig) -> ResearchTool:
        """Return a search tool matching the configured provider."""
        ...
