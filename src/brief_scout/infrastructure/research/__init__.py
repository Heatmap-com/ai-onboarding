"""Research infrastructure adapters."""

from brief_scout.infrastructure.research.fake_search_tool import FakeSearchTool
from brief_scout.infrastructure.research.tavily_search_tool import TavilyWebSearchTool

__all__ = ["FakeSearchTool", "TavilyWebSearchTool"]
