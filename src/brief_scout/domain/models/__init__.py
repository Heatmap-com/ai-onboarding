"""Domain models for Brief Scout.

This module exports all Pydantic models used across the application.
Models are organized by domain concern: intake, research, brief, and config.
"""

from brief_scout.domain.models.brief import (
    Brief,
    BriefSection,
    CreativeAngle,
)
from brief_scout.domain.models.config import (
    AppConfig,
    LLMProviderConfig,
    PromptsConfig,
    PromptTemplateConfig,
    TelemetryConfig,
)
from brief_scout.domain.models.intake import (
    ChatMessage,
    ChatSession,
    CreativeDirections,
    IntakeData,
)
from brief_scout.domain.models.research import (
    BrandAuditResult,
    CompetitorData,
    CompetitorScanResult,
    CustomerVoiceResult,
    HookMiningResult,
    ResearchBundle,
    TrendPulseResult,
)

__all__ = [
    # Intake models
    "ChatMessage",
    "ChatSession",
    "CreativeDirections",
    "IntakeData",
    # Research models
    "BrandAuditResult",
    "CompetitorData",
    "CompetitorScanResult",
    "CustomerVoiceResult",
    "HookMiningResult",
    "ResearchBundle",
    "TrendPulseResult",
    # Brief models
    "Brief",
    "BriefSection",
    "CreativeAngle",
    # Config models
    "AppConfig",
    "LLMProviderConfig",
    "PromptsConfig",
    "PromptTemplateConfig",
    "TelemetryConfig",
]
