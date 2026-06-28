"""Configuration models for the Brief Scout application."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    model_config = ConfigDict(frozen=False, extra="allow")

    adapter_class: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout_seconds: float = 30.0


class PromptTemplateConfig(BaseModel):
    """A single prompt template with system and user components."""

    model_config = ConfigDict(frozen=False)

    system: str = ""
    user: str = ""


class PromptsConfig(BaseModel):
    """All prompt templates organized by use case."""

    model_config = ConfigDict(frozen=False)

    extraction_system: str = ""
    research_brand_audit: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    research_competitor_scan: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    research_trend_pulse: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    research_customer_voice: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    research_hook_mining: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    synthesis: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)


class TelemetryConfig(BaseModel):
    """Telemetry and observability configuration."""

    model_config = ConfigDict(frozen=False)

    adapter: str = "local_file"
    log_level: str = "INFO"
    log_dir: str = "./logs"
    correlation_id_header: str = "x-correlation-id"


class AppConfig(BaseModel):
    """Root application configuration.

    Loaded from YAML files and validated with Pydantic.
    Supports environment-specific overlays.
    """

    model_config = ConfigDict(frozen=False)

    app_name: str = "Brief Scout"
    app_version: str = "1.0.0"
    default_llm_provider: str = "fake"
    llm_providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    storage_adapter: str = "in_memory"
    max_concurrent_research_calls: int = 5
    research_timeout_seconds: float = 60.0
    enable_streaming: bool = True

    def get_provider_config(self, provider_name: str) -> LLMProviderConfig:
        """Get configuration for a specific LLM provider.

        Args:
            provider_name: The name of the provider (e.g., 'fake', 'openai').

        Returns:
            The LLMProviderConfig for the named provider.

        Raises:
            KeyError: If the provider is not configured.
        """
        if provider_name not in self.llm_providers:
            raise KeyError(f"LLM provider '{provider_name}' not configured")
        return self.llm_providers[provider_name]
