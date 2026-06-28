"""Unit tests for YAMLConfigAdapter.

Exercises src/brief_scout/infrastructure/config/yaml_config_adapter.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from brief_scout.domain.errors import ConfigError
from brief_scout.domain.models.config import AppConfig, LLMProviderConfig
from brief_scout.infrastructure.config.config_merger import ConfigMerger
from brief_scout.infrastructure.config.env_interpolator import EnvInterpolator
from brief_scout.infrastructure.config.yaml_config_adapter import YAMLConfigAdapter


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with default and env YAML files."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    default = {
        "app_name": "Test App",
        "app_version": "1.0.0",
        "default_llm_provider": "fake",
        "llm_providers": {
            "fake": {
                "adapter_class": "brief_scout.infrastructure.llm.fake_llm_adapter.FakeLLMAdapter",
                "fixture_dir": "tests/fixtures/llm_responses",
                "default_fixture": "default",
                "latency_ms": 50,
            },
            "openai": {
                "adapter_class": "brief_scout.infrastructure.llm.openai_adapter.OpenAIAdapter",
                "api_key": "${OPENAI_API_KEY}",
                "model": "gpt-4o-mini",
            },
        },
        "prompts": {
            "extraction_system": "Extract: {{schema}}",
            "research_brand_audit": {
                "system": "audit system",
                "user": "audit {brand_name}",
            },
        },
        "telemetry": {
            "adapter": "local_file",
            "log_level": "INFO",
            "log_dir": "./logs",
        },
        "storage_adapter": "in_memory",
    }
    (cfg / "default.yaml").write_text(yaml.safe_dump(default))

    env = {
        "telemetry": {"log_level": "DEBUG"},
        "storage_adapter": "file_system",
    }
    (cfg / "test.yaml").write_text(yaml.safe_dump(env))
    return cfg


class TestYAMLConfigAdapter:
    """Tests for YAML configuration loading and access."""

    def test_should_load_default_config(self, config_dir: Path) -> None:
        """Adapter should load and validate default.yaml."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="missing")
        cfg = adapter.app_config

        assert isinstance(cfg, AppConfig)
        assert cfg.app_name == "Test App"
        assert cfg.app_version == "1.0.0"
        assert cfg.default_llm_provider == "fake"

    def test_should_merge_environment_overlay(self, config_dir: Path) -> None:
        """Adapter should deep-merge environment-specific overrides."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        cfg = adapter.app_config

        assert cfg.telemetry.log_level == "DEBUG"
        assert cfg.storage_adapter == "file_system"
        assert cfg.app_name == "Test App"  # preserved from default

    def test_should_interpolate_env_vars(
        self, config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Adapter should replace ${VAR_NAME} with environment values."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        provider = adapter.get_provider_config("openai")

        assert isinstance(provider, LLMProviderConfig)
        assert provider.api_key == "sk-test-key"

    def test_should_leave_missing_env_var_placeholder(self, config_dir: Path) -> None:
        """Adapter should leave placeholder unchanged if env var is missing."""
        os.environ.pop("OPENAI_API_KEY_PLACEHOLDER_TEST", None)
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        provider = adapter.get_provider_config("openai")

        assert "${OPENAI_API_KEY}" in provider.api_key

    def test_should_get_provider_config(self, config_dir: Path) -> None:
        """get_provider_config should return provider-specific config."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        provider = adapter.get_provider_config("fake")

        assert provider.adapter_class.endswith("FakeLLMAdapter")

    def test_should_raise_for_unknown_provider(self, config_dir: Path) -> None:
        """get_provider_config should raise KeyError for unknown providers."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        with pytest.raises(KeyError):
            adapter.get_provider_config("unknown")

    def test_should_get_prompt_template(self, config_dir: Path) -> None:
        """get_prompt_template should return a PromptTemplateConfig."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        template = adapter.get_prompt_template("research_brand_audit")

        assert template.system == "audit system"
        assert "{brand_name}" in template.user

    def test_should_get_string_prompt_template(self, config_dir: Path) -> None:
        """get_prompt_template should wrap string prompts into system/user."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        template = adapter.get_prompt_template("extraction_system")

        assert template.system == ""
        assert template.user == "Extract: {{schema}}"

    def test_should_raise_for_unknown_prompt_template(self, config_dir: Path) -> None:
        """get_prompt_template should raise KeyError for unknown templates."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        with pytest.raises(KeyError):
            adapter.get_prompt_template("unknown")

    def test_should_reload_config(self, config_dir: Path) -> None:
        """reload should clear cached config and force re-load."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir), env="test")
        _ = adapter.app_config
        adapter.reload()
        assert "app_config" not in adapter.__dict__

    def test_should_raise_when_default_config_missing(self, tmp_path: Path) -> None:
        """Adapter should raise ConfigError when default.yaml is missing."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        adapter = YAMLConfigAdapter(config_dir=str(empty_dir), env="test")

        with pytest.raises(ConfigError):
            _ = adapter.app_config

    def test_should_raise_on_invalid_yaml(self, tmp_path: Path) -> None:
        """Adapter should raise ConfigError when YAML is malformed."""
        cfg = tmp_path / "config"
        cfg.mkdir()
        (cfg / "default.yaml").write_text("not: valid: yaml: [")
        adapter = YAMLConfigAdapter(config_dir=str(cfg), env="test")

        with pytest.raises(ConfigError):
            _ = adapter.app_config

    def test_should_use_default_env_when_not_specified(self, config_dir: Path) -> None:
        """Default env should be 'development'."""
        adapter = YAMLConfigAdapter(config_dir=str(config_dir))
        # development.yaml doesn't exist in temp dir, so only default is loaded
        cfg = adapter.app_config
        assert cfg.app_name == "Test App"

    def test_deep_merge_replaces_non_dict_values(self) -> None:
        """Deep merge should replace non-dict leaf values."""
        merger = ConfigMerger()
        merged = merger.merge({"a": {"b": 1}}, {"a": {"b": 2}})
        assert merged == {"a": {"b": 2}}

    def test_interpolate_env_vars_recursively(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Interpolation should handle nested dicts and lists."""
        monkeypatch.setenv("TEST_KEY", "test_value")
        interpolator = EnvInterpolator()
        result = interpolator.interpolate(
            {"a": "${TEST_KEY}", "b": ["${TEST_KEY}"], "c": {"d": "${TEST_KEY}"}}
        )
        assert result == {"a": "test_value", "b": ["test_value"], "c": {"d": "test_value"}}
