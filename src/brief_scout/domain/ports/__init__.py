"""Domain ports — contracts that adapters must implement.

All ports use Python Protocol classes with structural subtyping.
This allows adapters to implement the contract without inheriting
from a base class, keeping the dependency graph clean.
"""

from brief_scout.domain.ports.config_port import ConfigurationPort
from brief_scout.domain.ports.llm_port import LLMPort, LLMResponse, Prompt
from brief_scout.domain.ports.storage_port import BriefStoragePort
from brief_scout.domain.ports.telemetry_port import (
    LogLevel,
    TelemetryEvent,
    TelemetryPort,
)

__all__ = [
    "LLMPort",
    "LLMResponse",
    "Prompt",
    "ConfigurationPort",
    "LogLevel",
    "TelemetryEvent",
    "TelemetryPort",
    "BriefStoragePort",
]
