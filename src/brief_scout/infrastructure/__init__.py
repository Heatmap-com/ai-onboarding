"""Infrastructure layer — concrete adapter implementations.

All adapters in this module implement the domain Ports defined in
``brief_scout.domain.ports``. The infrastructure layer is the outermost
ring of the hexagonal architecture — it depends on the domain layer,
never the reverse.

Adapters provided:
    - LLM: FakeLLMAdapter (primary), LangChainBaseAdapter (base for real adapters)
    - Config: YAMLConfigAdapter (YAML + env var interpolation)
    - Telemetry: LocalFileTelemetryAdapter (JSONL logs), StructuredLogger
    - Storage: InMemoryStorageAdapter, FileSystemStorageAdapter
"""

from brief_scout.infrastructure.config import YAMLConfigAdapter
from brief_scout.infrastructure.llm import FakeLLMAdapter, LangChainBaseAdapter
from brief_scout.infrastructure.storage import (
    FileSystemStorageAdapter,
    InMemoryStorageAdapter,
)
from brief_scout.infrastructure.telemetry import (
    LocalFileTelemetryAdapter,
    StructuredLogger,
    get_logger,
)

__all__ = [
    # LLM adapters
    "FakeLLMAdapter",
    "LangChainBaseAdapter",
    # Config adapters
    "YAMLConfigAdapter",
    # Telemetry adapters
    "LocalFileTelemetryAdapter",
    "StructuredLogger",
    "get_logger",
    # Storage adapters
    "InMemoryStorageAdapter",
    "FileSystemStorageAdapter",
]
