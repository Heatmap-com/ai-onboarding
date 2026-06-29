"""Storage adapter factory — maps adapter_id to storage implementations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from brief_scout.domain.ports.logger_port import LoggerPort
from brief_scout.domain.ports.storage_port import BriefStoragePort
from brief_scout.infrastructure.storage.file_system_adapter import (
    FileSystemStorageAdapter,
)
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)

_Builder = Callable[[str, str | Path, LoggerPort | None], BriefStoragePort]


def _build_in_memory(
    _adapter_id: str,
    _data_dir: str | Path,
    _logger: LoggerPort | None,
) -> BriefStoragePort:
    """In-memory storage adapter builder."""
    return InMemoryStorageAdapter()


def _build_file_system(
    _adapter_id: str,
    data_dir: str | Path,
    logger: LoggerPort | None,
) -> BriefStoragePort:
    """File-system storage adapter builder."""
    return FileSystemStorageAdapter(data_dir=str(data_dir), logger=logger)


class StorageAdapterFactory:
    """Factory that constructs storage adapters by adapter_id.

    New adapters are added by registering a builder callable; no special-case
    logic is required in ``create()``.
    """

    _REGISTRY: dict[str, _Builder] = {
        "in_memory": _build_in_memory,
        "file_system": _build_file_system,
    }

    def __init__(
        self,
        registry: dict[str, _Builder] | None = None,
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
        builder = self._registry.get(adapter_id)
        if builder is None:
            raise ValueError(f"Unknown storage adapter_id: {adapter_id}")

        return builder(adapter_id, data_dir, logger)

    def register(
        self,
        adapter_id: str,
        builder: _Builder,
    ) -> None:
        """Register a new storage adapter builder."""
        self._registry[adapter_id] = builder

    @property
    def supported_adapters(self) -> list[str]:
        """Return the list of registered adapter identifiers."""
        return list(self._registry.keys())
