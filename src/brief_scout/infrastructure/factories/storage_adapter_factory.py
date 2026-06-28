"""Storage adapter factory — maps adapter_id to storage implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from brief_scout.infrastructure.storage.file_system_adapter import (
    FileSystemStorageAdapter,
)
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)

if TYPE_CHECKING:
    from pathlib import Path

    from brief_scout.domain.ports.logger_port import LoggerPort
    from brief_scout.domain.ports.storage_port import BriefStoragePort


class StorageAdapterFactory:
    """Factory that constructs storage adapters by adapter_id."""

    _REGISTRY: dict[str, type[Any]] = {
        "in_memory": InMemoryStorageAdapter,
        "file_system": FileSystemStorageAdapter,
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
        data_dir: str | Path = "./data",
        logger: LoggerPort | None = None,
    ) -> BriefStoragePort:
        """Create a storage adapter from configuration.

        Args:
            adapter_id: Registered storage adapter identifier.
            data_dir: Root data directory for file_system adapter.
            logger: Optional logger for corrupted-file diagnostics.

        Returns:
            Instantiated BriefStoragePort implementation.

        Raises:
            ValueError: If the adapter_id is not registered.
        """
        adapter_cls = self._registry.get(adapter_id)
        if adapter_cls is None:
            raise ValueError(f"Unknown storage adapter_id: {adapter_id}")

        if adapter_cls is FileSystemStorageAdapter:
            return cast(
                "BriefStoragePort",
                FileSystemStorageAdapter(data_dir=str(data_dir), logger=logger),
            )

        return cast("BriefStoragePort", adapter_cls())
