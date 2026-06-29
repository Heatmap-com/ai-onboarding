"""Tavily web search tool implementation."""

from __future__ import annotations

from typing import Any

import httpx

from brief_scout.domain.ports.research_tool_port import ResearchTool, SearchResult


class TavilyWebSearchTool(ResearchTool):
    """Search tool that calls the Tavily search API."""

    DEFAULT_BASE_URL: str = "https://api.tavily.com"

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        search_depth: str = "basic",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Tavily search tool.

        Args:
            api_key: Tavily API key.
            base_url: Optional Tavily API base URL override.
            search_depth: Tavily search depth (``basic`` or ``advanced``).
            client: Optional injected httpx async client for testing.
        """
        self._api_key = api_key
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._search_depth = search_depth
        self._client = client

    async def search(self, query: str, **kwargs: Any) -> SearchResult:
        """Execute a Tavily search and return snippets."""
        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.post(
                f"{self._base_url}/search",
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": self._search_depth,
                    **kwargs,
                },
            )
            response.raise_for_status()
            data = response.json()
            snippets = [
                result.get("content", "")
                for result in data.get("results", [])
                if result.get("content")
            ]
            return SearchResult(query=query, snippets=snippets)
        finally:
            if self._client is None:
                await client.aclose()
