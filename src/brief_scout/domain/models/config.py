"""Configuration models for the Brief Scout application."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider.

    ``adapter_id`` is a generic identifier string. The integration layer
    maps identifiers to concrete adapter implementations via a registry.
    The legacy ``adapter_class`` key is still accepted in YAML for backward
    compatibility and is normalized into ``adapter_id``.
    """

    model_config = ConfigDict(frozen=False, extra="allow")

    adapter_id: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def _normalize_adapter_id(self) -> LLMProviderConfig:
        """Fall back to legacy ``adapter_class`` when ``adapter_id`` is absent."""
        if not self.adapter_id:
            extra = self.model_extra or {}
            legacy = extra.get("adapter_class") or extra.get("adapter_id")
            if legacy:
                self.adapter_id = str(legacy)
        return self

    @property
    def adapter_class(self) -> str:
        """Backward-compatible alias that prefers the explicit ``adapter_class`` extra."""
        extra = self.model_extra or {}
        return str(extra.get("adapter_class", self.adapter_id))

    @property
    def extras(self) -> dict[str, object]:
        """Return provider-specific extra settings as a generic config bag."""
        return {k: v for k, v in (self.model_extra or {}).items() if k != "adapter_class"}


class PromptTemplateConfig(BaseModel):
    """A single prompt template with system and user components."""

    model_config = ConfigDict(frozen=False)

    system: str = ""
    user: str = ""


class PromptsConfig(BaseModel):
    """All prompt templates organized by use case.

    Research prompts are stored in an open ``research_steps`` catalog so
    new research steps can be added in YAML without touching this model.
    Legacy flat keys such as ``research_brand_audit`` are automatically
    migrated into the catalog.
    """

    model_config = ConfigDict(frozen=False, extra="allow")

    extraction_system: str = ""
    synthesis: PromptTemplateConfig = Field(default_factory=PromptTemplateConfig)
    research_steps: dict[str, PromptTemplateConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _collect_research_prompts(cls, data: object) -> object:
        """Move legacy flat research prompt keys into ``research_steps``."""
        if not isinstance(data, dict):
            return data
        normalized: dict[str, object] = dict(data)
        steps: dict[str, PromptTemplateConfig] = {}
        legacy_steps = normalized.pop("research_steps", None)
        if isinstance(legacy_steps, dict):
            for key, value in legacy_steps.items():
                if isinstance(value, dict):
                    steps[key] = PromptTemplateConfig.model_validate(value)
                elif isinstance(value, PromptTemplateConfig):
                    steps[key] = value

        for key in list(normalized):
            if key.startswith("research_") and isinstance(normalized[key], dict):
                step_name = key[len("research_") :]
                steps[step_name] = PromptTemplateConfig.model_validate(normalized.pop(key))

        normalized["research_steps"] = steps
        return normalized

    @field_validator("research_steps", mode="before")
    @classmethod
    def _ensure_prompt_template_objects(
        cls,
        value: object,
    ) -> dict[str, PromptTemplateConfig]:
        """Ensure every research step value is a ``PromptTemplateConfig``."""
        if not isinstance(value, dict):
            return {}
        result: dict[str, PromptTemplateConfig] = {}
        for key, item in value.items():
            if isinstance(item, PromptTemplateConfig):
                result[key] = item
            elif isinstance(item, dict):
                result[key] = PromptTemplateConfig.model_validate(item)
        return result

    @property
    def research_brand_audit(self) -> PromptTemplateConfig:
        """Backward-compatible accessor for the brand audit prompt."""
        return self.research_steps.get("brand_audit", PromptTemplateConfig())

    @property
    def research_competitor_scan(self) -> PromptTemplateConfig:
        """Backward-compatible accessor for the competitor scan prompt."""
        return self.research_steps.get("competitor_scan", PromptTemplateConfig())

    @property
    def research_trend_pulse(self) -> PromptTemplateConfig:
        """Backward-compatible accessor for the trend pulse prompt."""
        return self.research_steps.get("trend_pulse", PromptTemplateConfig())

    @property
    def research_customer_voice(self) -> PromptTemplateConfig:
        """Backward-compatible accessor for the customer voice prompt."""
        return self.research_steps.get("customer_voice", PromptTemplateConfig())

    @property
    def research_hook_mining(self) -> PromptTemplateConfig:
        """Backward-compatible accessor for the hook mining prompt."""
        return self.research_steps.get("hook_mining", PromptTemplateConfig())


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
            provider_name: The name of the provider (e.g. 'fake', 'openai').

        Returns:
            The LLMProviderConfig for the named provider.

        Raises:
            KeyError: If the provider is not configured.
        """
        if provider_name not in self.llm_providers:
            raise KeyError(f"LLM provider '{provider_name}' not configured")
        return self.llm_providers[provider_name]
