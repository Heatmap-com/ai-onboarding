"""Research tool port — abstraction for external search/retrieval tools."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Result from a research search tool."""

    query: str = ""
    snippets: list[str] = Field(default_factory=list)


@runtime_checkable
class ResearchTool(Protocol):
    """Port for tools that retrieve external context for research steps."""

    async def search(self, query: str, **kwargs: Any) -> SearchResult:
        """Execute a search and return relevant snippets.

        Args:
            query: Search query string.
            **kwargs: Provider-specific options.

        Returns:
            A ``SearchResult`` containing retrieved snippets.
        """
        ...
