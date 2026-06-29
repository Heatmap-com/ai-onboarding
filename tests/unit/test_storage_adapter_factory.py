"""Unit tests for the registry-based storage adapter factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from brief_scout.infrastructure.factories.storage_adapter_factory import (
    StorageAdapterFactory,
)
from brief_scout.infrastructure.storage.file_system_adapter import (
    FileSystemStorageAdapter,
)
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)

if TYPE_CHECKING:
    from brief_scout.domain.ports.storage_port import BriefStoragePort


class TestStorageAdapterFactory:
    """Tests for StorageAdapterFactory registry behavior."""

    def test_should_create_in_memory_adapter(self) -> None:
        """Factory should create InMemoryStorageAdapter by id."""
        factory = StorageAdapterFactory()
        adapter = factory.create("in_memory")
        assert isinstance(adapter, InMemoryStorageAdapter)

    def test_should_create_file_system_adapter(self, tmp_path: Path) -> None:
        """Factory should create FileSystemStorageAdapter by id."""
        factory = StorageAdapterFactory()
        adapter = factory.create("file_system", data_dir=str(tmp_path / "data"))
        assert isinstance(adapter, FileSystemStorageAdapter)

    def test_should_reject_unknown_adapter(self) -> None:
        """Factory should raise for unregistered adapter ids."""
        factory = StorageAdapterFactory()
        with pytest.raises(ValueError, match="Unknown storage adapter_id"):
            factory.create("unknown")

    def test_should_support_custom_registry(self) -> None:
        """Factory should use a custom registry when provided."""

        def _build_custom(
            _adapter_id: str,
            _data_dir: str | Path,
            _logger: Any | None,
        ) -> BriefStoragePort:
            return InMemoryStorageAdapter()

        factory = StorageAdapterFactory(registry={"custom": _build_custom})
        adapter = factory.create("custom")
        assert isinstance(adapter, InMemoryStorageAdapter)
        assert factory.supported_adapters == ["custom"]

    def test_should_list_supported_adapters(self) -> None:
        """Factory should expose registered adapter identifiers."""
        factory = StorageAdapterFactory()
        assert set(factory.supported_adapters) == {"in_memory", "file_system"}
