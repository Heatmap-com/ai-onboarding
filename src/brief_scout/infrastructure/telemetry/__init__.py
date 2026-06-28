"""Telemetry infrastructure adapters.

Provides telemetry implementations that conform to the TelemetryPort Protocol.
The LocalFileTelemetryAdapter writes structured JSONL logs locally,
while StructuredLogger provides a convenience wrapper around structlog.
"""

from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)
from brief_scout.infrastructure.telemetry.structured_logger import (
    StructuredLogger,
    get_logger,
)

__all__ = [
    "LocalFileTelemetryAdapter",
    "StructuredLogger",
    "get_logger",
]
