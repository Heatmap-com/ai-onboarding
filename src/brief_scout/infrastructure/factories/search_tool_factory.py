"""Search tool factory — maps configured provider to a ``ResearchTool``."""

from __future__ import annotations

from collections.abc import Callable

from brief_scout.domain.models.config import SearchConfig
from brief_scout.domain.ports.research_tool_port import ResearchTool
from brief_scout.domain.ports.search_tool_factory_port import SearchToolFactory
from brief_scout.infrastructure.research.fake_search_tool import FakeSearchTool
from brief_scout.infrastructure.research.tavily_search_tool import TavilyWebSearchTool

_Builder = Callable[[SearchConfig], ResearchTool]


def _build_fake(_config: SearchConfig) -> ResearchTool:
    """No-op search tool for offline mode or missing credentials."""
    return FakeSearchTool()


def _build_tavily(config: SearchConfig) -> ResearchTool:
    """Tavily-backed search tool when an API key is available."""
    if not config.api_key:
        return FakeSearchTool()
    return TavilyWebSearchTool(
        api_key=config.api_key,
        base_url=config.base_url or "",
        search_depth=config.search_depth,
    )


class DefaultSearchToolFactory(SearchToolFactory):
    """Registry-based factory for search tools.

    Adding a new provider only requires registering a builder callable; the
    composition root and this class do not need to change.
    """

    _REGISTRY: dict[str, _Builder] = {
        "fake": _build_fake,
        "tavily": _build_tavily,
    }

    def __init__(self, registry: dict[str, _Builder] | None = None) -> None:
        """Initialize with an optional custom registry."""
        self._registry = registry or self._REGISTRY

    def create(self, config: SearchConfig) -> ResearchTool:
        """Create a search tool from configuration.

        Unknown providers fall back to the fake tool so the pipeline remains
        runnable without external credentials.
        """
        builder = self._registry.get(config.provider, _build_fake)
        return builder(config)

    def register(
        self,
        provider: str,
        builder: _Builder,
    ) -> None:
        """Register a new provider builder (useful for tests and extensions)."""
        self._registry[provider] = builder

    @property
    def supported_providers(self) -> list[str]:
        """Return the list of registered provider identifiers."""
        return list(self._registry.keys())
