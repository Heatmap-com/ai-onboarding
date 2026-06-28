"""Unit tests for configuration models and validators."""

from __future__ import annotations

import pytest

from brief_scout.domain.models.config import (
    AppConfig,
    LLMProviderConfig,
    PromptsConfig,
    PromptTemplateConfig,
)


class TestLLMProviderConfig:
    """Tests for LLMProviderConfig normalization."""

    def test_adapter_id_defaults_to_empty(self) -> None:
        """A fresh config should have an empty adapter_id."""
        config = LLMProviderConfig()
        assert config.adapter_id == ""

    def test_legacy_adapter_class_normalized(self) -> None:
        """Legacy ``adapter_class`` extra should be copied to ``adapter_id``."""
        config = LLMProviderConfig(adapter_id="", adapter_class="openai_adapter")
        assert config.adapter_id == "openai_adapter"

    def test_adapter_class_property_prefers_extra(self) -> None:
        """The backward-compat property should prefer the explicit extra."""
        config = LLMProviderConfig(
            adapter_id="new",
            adapter_class="legacy",
        )
        assert config.adapter_class == "legacy"

    def test_excludes_adapter_class_from_extras(self) -> None:
        """``extras`` should not include the legacy adapter_class key."""
        config = LLMProviderConfig(
            adapter_id="openai",
            adapter_class="openai_adapter",
            temperature=0.5,
        )
        assert "adapter_class" not in config.extras
        assert "temperature" not in config.extras


class TestPromptsConfig:
    """Tests for the dynamic prompt catalog."""

    def test_legacy_research_prompts_migrated(self) -> None:
        """Flat legacy keys should be moved into ``research_steps``."""
        prompts = PromptsConfig(
            research_brand_audit={"system": "sys", "user": "brand {brand_name}"},
            research_competitor_scan={"system": "sys", "user": "competitors"},
        )
        assert "brand_audit" in prompts.research_steps
        assert prompts.research_steps["brand_audit"].user == "brand {brand_name}"
        assert "competitor_scan" in prompts.research_steps

    def test_backward_compatible_accessors(self) -> None:
        """Legacy property accessors should return step templates."""
        prompts = PromptsConfig(
            research_steps={
                "brand_audit": PromptTemplateConfig(system="s", user="u"),
            },
        )
        assert prompts.research_brand_audit.system == "s"
        assert prompts.research_hook_mining.system == ""


class TestAppConfig:
    """Tests for the root application config."""

    def test_get_provider_config(self) -> None:
        """Provider configs should be retrievable by name."""
        config = AppConfig(
            llm_providers={
                "fake": LLMProviderConfig(adapter_id="fake"),
            },
        )
        assert config.get_provider_config("fake").adapter_id == "fake"

    def test_get_provider_config_missing(self) -> None:
        """Missing provider configs should raise KeyError."""
        config = AppConfig()
        with pytest.raises(KeyError, match="LLM provider 'openai' not configured"):
            config.get_provider_config("openai")
