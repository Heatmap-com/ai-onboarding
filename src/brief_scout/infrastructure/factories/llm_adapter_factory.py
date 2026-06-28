"""LLM adapter factory — maps adapter_id to concrete LLM adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from brief_scout.infrastructure.llm.claude_adapter import ClaudeAdapter
from brief_scout.infrastructure.llm.fake_llm_adapter import FakeLLMAdapter
from brief_scout.infrastructure.llm.kimi_adapter import KimiAdapter
from brief_scout.infrastructure.llm.openai_adapter import OpenAIAdapter

if TYPE_CHECKING:
    from brief_scout.domain.models.config import LLMProviderConfig
    from brief_scout.domain.ports.event_recorder_port import EventRecorder
    from brief_scout.domain.ports.llm_port import LLMPort
    from brief_scout.domain.ports.logger_port import LoggerPort


class LLMAdapterFactory:
    """Factory that constructs LLM adapters by adapter_id."""

    _REGISTRY: dict[str, type[Any]] = {
        "fake": FakeLLMAdapter,
        "openai": OpenAIAdapter,
        "kimi": KimiAdapter,
        "claude": ClaudeAdapter,
    }

    def __init__(
        self,
        registry: dict[str, type[Any]] | None = None,
    ) -> None:
        """Initialize the factory.

        Args:
            registry: Optional custom adapter registry.
        """
        self._registry = registry or self._REGISTRY

    def create(
        self,
        provider_config: LLMProviderConfig,
        telemetry: LoggerPort | EventRecorder | None = None,
    ) -> LLMPort:
        """Create an LLM adapter from provider configuration.

        Args:
            provider_config: Configuration for the LLM provider.
            telemetry: Optional logger/event recorder port.

        Returns:
            Instantiated LLMPort implementation.

        Raises:
            ValueError: If the adapter_id is not registered.
        """
        adapter_id = getattr(provider_config, "adapter_id", None)
        # Backward compatibility with adapter_class until Agent 1 migrates config.
        if not adapter_id:
            adapter_id = self._derive_id_from_class(provider_config.adapter_class)

        adapter_cls = self._registry.get(adapter_id)
        if adapter_cls is None:
            raise ValueError(f"Unknown LLM adapter_id: {adapter_id}")

        extras = provider_config.model_extra or {}
        if adapter_id == "fake":
            return FakeLLMAdapter(
                fixture_dir=extras.get("fixture_dir", "tests/fixtures/llm_responses"),
                default_fixture=extras.get("default_fixture", "default"),
                latency_ms=extras.get("latency_ms", 50.0),
                telemetry=telemetry,
                demo_journey_path=extras.get("demo_journey_path"),
            )

        return cast(
            "LLMPort",
            adapter_cls(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url or None,
                model=provider_config.model,
                temperature=provider_config.temperature,
                max_tokens=provider_config.max_tokens,
                timeout_seconds=provider_config.timeout_seconds,
                telemetry=telemetry,
            ),
        )

    @staticmethod
    def _derive_id_from_class(adapter_class: str) -> str:
        """Derive adapter_id from legacy adapter_class path."""
        if not adapter_class:
            return "fake"
        if adapter_class.endswith("FakeLLMAdapter"):
            return "fake"
        if adapter_class.endswith("OpenAIAdapter"):
            return "openai"
        if adapter_class.endswith("KimiAdapter"):
            return "kimi"
        if adapter_class.endswith("ClaudeAdapter"):
            return "claude"
        return adapter_class
