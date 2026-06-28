"""Telemetry adapter factory — maps adapter_id to telemetry implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from brief_scout.infrastructure.telemetry.local_file_adapter import (
    LocalFileTelemetryAdapter,
)

if TYPE_CHECKING:
    from brief_scout.domain.models.config import TelemetryConfig
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class TelemetryAdapterFactory:
    """Factory that constructs telemetry adapters by adapter_id."""

    _REGISTRY: dict[str, type[Any]] = {
        "local_file": LocalFileTelemetryAdapter,
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
        adapter_id: str,
        config: TelemetryConfig | None = None,
    ) -> TelemetryPort:
        """Create a telemetry adapter from configuration.

        Args:
            adapter_id: Registered telemetry adapter identifier.
            config: Telemetry configuration.

        Returns:
            Instantiated TelemetryPort implementation.

        Raises:
            ValueError: If the adapter_id is not registered.
        """
        adapter_cls = self._registry.get(adapter_id)
        if adapter_cls is None:
            raise ValueError(f"Unknown telemetry adapter_id: {adapter_id}")

        log_dir = "./logs"
        log_level = "INFO"
        if config is not None:
            log_dir = config.log_dir
            log_level = config.log_level

        return cast("TelemetryPort", adapter_cls(log_dir=log_dir, log_level=log_level))
