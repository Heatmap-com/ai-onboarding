"""Storage infrastructure adapters.

Provides storage implementations that conform to the BriefStoragePort Protocol.

- InMemoryStorageAdapter: Non-persistent, dictionary-based storage for MVP.
- FileSystemStorageAdapter: Persistent JSON file storage for single-instance deployments.

Both adapters implement the same Protocol, allowing transparent swapping
without changes to domain or application layers.
"""

from brief_scout.infrastructure.storage.file_system_adapter import FileSystemStorageAdapter
from brief_scout.infrastructure.storage.in_memory_adapter import InMemoryStorageAdapter

__all__ = [
    "InMemoryStorageAdapter",
    "FileSystemStorageAdapter",
]
