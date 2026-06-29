"""Unit tests for the registry-based search tool factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.models.config import SearchConfig
from brief_scout.infrastructure.factories.search_tool_factory import (
    DefaultSearchToolFactory,
)
from brief_scout.infrastructure.research.fake_search_tool import FakeSearchTool
from brief_scout.infrastructure.research.tavily_search_tool import TavilyWebSearchTool

if TYPE_CHECKING:
    from brief_scout.domain.ports.research_tool_port import ResearchTool


class TestDefaultSearchToolFactory:
    """Tests for DefaultSearchToolFactory registry behavior."""

    def test_should_create_fake_tool_by_default(self) -> None:
        """Factory should return FakeSearchTool for the fake provider."""
        factory = DefaultSearchToolFactory()
        tool = factory.create(SearchConfig(provider="fake"))
        assert isinstance(tool, FakeSearchTool)

    def test_should_create_tavily_tool_when_key_present(self) -> None:
        """Factory should return TavilyWebSearchTool when key is present."""
        factory = DefaultSearchToolFactory()
        tool = factory.create(
            SearchConfig(provider="tavily", api_key="secret", search_depth="advanced"),
        )
        assert isinstance(tool, TavilyWebSearchTool)

    def test_should_fallback_to_fake_when_tavily_key_missing(self) -> None:
        """Factory should fall back to FakeSearchTool when Tavily key is missing."""
        factory = DefaultSearchToolFactory()
        tool = factory.create(SearchConfig(provider="tavily"))
        assert isinstance(tool, FakeSearchTool)

    def test_should_fallback_to_fake_for_unknown_provider(self) -> None:
        """Factory should fall back to FakeSearchTool for unknown providers."""
        factory = DefaultSearchToolFactory()
        tool = factory.create(SearchConfig(provider="unknown"))
        assert isinstance(tool, FakeSearchTool)

    def test_should_support_custom_registry(self) -> None:
        """Factory should use a custom registry when provided."""

        def _build_custom(_config: SearchConfig) -> ResearchTool:
            return FakeSearchTool()

        factory = DefaultSearchToolFactory(registry={"custom": _build_custom})
        tool = factory.create(SearchConfig(provider="custom"))
        assert isinstance(tool, FakeSearchTool)
        assert factory.supported_providers == ["custom"]

    def test_should_register_new_provider(self) -> None:
        """Factory should allow runtime registration of new providers."""
        factory = DefaultSearchToolFactory()

        def _build_new(_config: SearchConfig) -> ResearchTool:
            return FakeSearchTool()

        factory.register("new_provider", _build_new)
        assert "new_provider" in factory.supported_providers
        tool = factory.create(SearchConfig(provider="new_provider"))
        assert isinstance(tool, FakeSearchTool)
