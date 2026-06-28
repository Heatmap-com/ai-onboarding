"""Domain ports — contracts that adapters must implement.

All ports use Python Protocol classes with structural subtyping.
This allows adapters to implement the contract without inheriting
from a base class, keeping the dependency graph clean.
"""

from brief_scout.domain.ports.app_config_provider_port import AppConfigProvider
from brief_scout.domain.ports.completion_port import CompletionPort, StructuredCompletionPort
from brief_scout.domain.ports.config_port import ConfigurationPort
from brief_scout.domain.ports.correlation_context_port import CorrelationContext
from brief_scout.domain.ports.event_recorder_port import EventRecorder
from brief_scout.domain.ports.journey_source_port import JourneySource
from brief_scout.domain.ports.llm_port import LLMPort, LLMResponse, Prompt
from brief_scout.domain.ports.logger_port import LoggerPort
from brief_scout.domain.ports.prompt_template_provider_port import PromptTemplateProvider
from brief_scout.domain.ports.provider_config_source_port import ProviderConfigSource
from brief_scout.domain.ports.reloadable_config_port import ReloadableConfig
from brief_scout.domain.ports.session_lister_port import SessionLister
from brief_scout.domain.ports.session_storage_port import SessionStoragePort
from brief_scout.domain.ports.span_context_port import SpanContext
from brief_scout.domain.ports.storage_port import BriefStoragePort
from brief_scout.domain.ports.telemetry_port import (
    LogLevel,
    TelemetryEvent,
    TelemetryPort,
)
from brief_scout.domain.ports.template_renderer_port import TemplateRenderer

__all__ = [
    "AppConfigProvider",
    "BriefStoragePort",
    "CompletionPort",
    "ConfigurationPort",
    "CorrelationContext",
    "EventRecorder",
    "JourneySource",
    "LLMPort",
    "LLMResponse",
    "LoggerPort",
    "Prompt",
    "PromptTemplateProvider",
    "ProviderConfigSource",
    "ReloadableConfig",
    "SessionLister",
    "SessionStoragePort",
    "SpanContext",
    "StructuredCompletionPort",
    "TemplateRenderer",
    "TelemetryEvent",
    "TelemetryPort",
    "LogLevel",
]
