"""Fake search tool for testing and offline development."""

from __future__ import annotations

from brief_scout.domain.ports.research_tool_port import ResearchTool, SearchResult


class FakeSearchTool(ResearchTool):
    """Returns canned snippets based on simple keyword matching.

    Useful for tests and local development without a live search API key.
    """

    def __init__(
        self,
        snippets: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize with optional canned snippets keyed by query substring."""
        self._snippets = snippets or {
            "nike": [
                "Nike is a global sportswear brand known for 'Just Do It'.",
                "Nike sponsors elite athletes and emphasizes performance.",
            ],
            "adidas": [
                "Adidas competes heavily in soccer and lifestyle footwear.",
            ],
            "trends": [
                "Athleisure and sustainability are dominant trends in sportswear.",
            ],
            "customer": [
                "Customers value comfort, style, and brand authenticity.",
            ],
        }

    async def search(self, query: str, **_kwargs: object) -> SearchResult:
        """Return snippets whose key appears in the query."""
        lower_query = query.lower()
        matched: list[str] = []
        for key, snippets in self._snippets.items():
            if key in lower_query:
                matched.extend(snippets)
        if not matched:
            matched = ["No relevant offline snippets found."]
        return SearchResult(query=query, snippets=matched)
