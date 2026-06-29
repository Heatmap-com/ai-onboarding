"""Research step implementations for the research pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.research_tool_port import ResearchTool


def _format_search_results(snippets: list[str]) -> str:
    """Format search snippets into a prompt-friendly bullet list."""
    if not snippets:
        return "No external search results available."
    return "\n".join(f"- {snippet}" for snippet in snippets)


async def _search_context(
    tool: ResearchTool | None,
    query: str,
) -> str:
    """Retrieve and format search context when a tool is available."""
    if tool is None:
        return "No external search results available."
    result = await tool.search(query)
    return _format_search_results(result.snippets)


@runtime_checkable
class ResearchStep(Protocol):
    """A single pluggable research step."""

    name: str

    async def execute(self, intake_data: IntakeData) -> BaseModel:
        """Execute the step and return a typed result."""
        ...
