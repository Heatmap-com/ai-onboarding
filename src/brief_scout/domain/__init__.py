"""Domain layer — business entities, value objects, ports, and services.

This is the innermost layer of the hexagonal architecture. It contains:
- Models: Pydantic data models representing business entities
- Ports: Protocol interfaces that adapters must implement
- Services: Business logic that operates on domain models
- Errors: Custom exception hierarchy

The domain layer has NO external dependencies. All dependencies point inward.
"""

# Models
# Errors
from brief_scout.domain.errors import (
    BriefScoutError,
    ConfigError,
    LLMCallError,
    ResearchPipelineError,
    SynthesisError,
    ValidationError,
)
from brief_scout.domain.models import (
    AppConfig,
    BrandAuditResult,
    Brief,
    BriefSection,
    ChatMessage,
    ChatSession,
    CompetitorData,
    CompetitorScanResult,
    CreativeAngle,
    CreativeDirections,
    CustomerVoiceResult,
    HookMiningResult,
    IntakeData,
    LLMProviderConfig,
    PromptsConfig,
    PromptTemplateConfig,
    ResearchBundle,
    TelemetryConfig,
    TrendPulseResult,
)

# Ports
from brief_scout.domain.ports import (
    BriefStoragePort,
    ConfigurationPort,
    LLMPort,
    LLMResponse,
    LogLevel,
    Prompt,
    TelemetryEvent,
    TelemetryPort,
)

# Services
from brief_scout.domain.services import (
    CompletenessChecker,
    CompletenessResult,
)

__all__ = [
    # Models - Intake
    "ChatMessage",
    "ChatSession",
    "CreativeDirections",
    "IntakeData",
    # Models - Research
    "BrandAuditResult",
    "CompetitorData",
    "CompetitorScanResult",
    "CustomerVoiceResult",
    "HookMiningResult",
    "ResearchBundle",
    "TrendPulseResult",
    # Models - Brief
    "Brief",
    "BriefSection",
    "CreativeAngle",
    # Models - Config
    "AppConfig",
    "LLMProviderConfig",
    "PromptsConfig",
    "PromptTemplateConfig",
    "TelemetryConfig",
    # Ports
    "LLMPort",
    "LLMResponse",
    "Prompt",
    "ConfigurationPort",
    "LogLevel",
    "TelemetryEvent",
    "TelemetryPort",
    "BriefStoragePort",
    # Services
    "CompletenessChecker",
    "CompletenessResult",
    # Errors
    "BriefScoutError",
    "ConfigError",
    "LLMCallError",
    "ResearchPipelineError",
    "SynthesisError",
    "ValidationError",
]
