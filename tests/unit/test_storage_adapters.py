"""Unit tests for source storage adapters.

Exercises:
- src/brief_scout/infrastructure/storage/in_memory_adapter.py
- src/brief_scout/infrastructure/storage/file_system_adapter.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brief_scout.domain.models.brief import Brief
from brief_scout.domain.models.intake import ChatSession, IntakeData
from brief_scout.infrastructure.storage.file_system_adapter import (
    FileSystemStorageAdapter,
)
from brief_scout.infrastructure.storage.in_memory_adapter import (
    InMemoryStorageAdapter,
)


class TestInMemoryStorageAdapter:
    """Tests for InMemoryStorageAdapter."""

    @pytest.fixture
    def storage(self) -> InMemoryStorageAdapter:
        """Provide a fresh in-memory storage adapter."""
        return InMemoryStorageAdapter()

    @pytest.mark.asyncio
    async def test_should_save_and_get_session(self, storage: InMemoryStorageAdapter) -> None:
        """save_session and get_session should round-trip a ChatSession."""
        session = ChatSession()
        await storage.save_session(session)

        retrieved = await storage.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_should_return_none_for_missing_session(
        self, storage: InMemoryStorageAdapter
    ) -> None:
        """get_session should return None for unknown IDs."""
        assert await storage.get_session("nonexistent") is None

    @pytest.mark.asyncio
    async def test_should_save_and_get_brief(self, storage: InMemoryStorageAdapter) -> None:
        """save_brief and get_brief should round-trip a Brief."""
        session = ChatSession()
        brief = Brief(brand_name="Nike", primary_goal="acquisition")
        await storage.save_brief(session.session_id, brief)

        retrieved = await storage.get_brief(session.session_id)
        assert retrieved is not None
        assert retrieved.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_should_return_none_for_missing_brief(
        self, storage: InMemoryStorageAdapter
    ) -> None:
        """get_brief should return None for unknown IDs."""
        assert await storage.get_brief("nonexistent") is None

    @pytest.mark.asyncio
    async def test_should_list_sessions_newest_first(self, storage: InMemoryStorageAdapter) -> None:
        """list_sessions should return sessions sorted by created_at descending."""
        session1 = ChatSession()
        session2 = ChatSession()
        await storage.save_session(session1)
        await storage.save_session(session2)

        sessions = await storage.list_sessions(limit=10)
        assert len(sessions) == 2
        assert sessions[0].created_at >= sessions[1].created_at

    @pytest.mark.asyncio
    async def test_should_respect_list_limit(self, storage: InMemoryStorageAdapter) -> None:
        """list_sessions should respect the limit parameter."""
        for _ in range(5):
            await storage.save_session(ChatSession())

        sessions = await storage.list_sessions(limit=2)
        assert len(sessions) == 2


class TestFileSystemStorageAdapter:
    """Tests for FileSystemStorageAdapter."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> FileSystemStorageAdapter:
        """Provide a FileSystemStorageAdapter writing to a temp directory."""
        return FileSystemStorageAdapter(data_dir=str(tmp_path / "data"))

    @pytest.mark.asyncio
    async def test_should_create_directories_on_init(self, tmp_path: Path) -> None:
        """Constructor should create sessions and briefs directories."""
        FileSystemStorageAdapter(data_dir=str(tmp_path / "data2"))
        assert (tmp_path / "data2" / "sessions").exists()
        assert (tmp_path / "data2" / "briefs").exists()

    @pytest.mark.asyncio
    async def test_should_save_and_get_session(self, storage: FileSystemStorageAdapter) -> None:
        """save_session and get_session should persist to disk."""
        session = ChatSession(intake_data=IntakeData(brand_name="Nike"))
        await storage.save_session(session)

        retrieved = await storage.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.intake_data.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_should_return_none_for_missing_session(
        self, storage: FileSystemStorageAdapter
    ) -> None:
        """get_session should return None for unknown IDs."""
        assert await storage.get_session("missing") is None

    @pytest.mark.asyncio
    async def test_should_save_and_get_brief(self, storage: FileSystemStorageAdapter) -> None:
        """save_brief and get_brief should persist to disk."""
        session = ChatSession()
        brief = Brief(brand_name="Nike", primary_goal="acquisition")
        await storage.save_brief(session.session_id, brief)

        retrieved = await storage.get_brief(session.session_id)
        assert retrieved is not None
        assert retrieved.brand_name == "Nike"

    @pytest.mark.asyncio
    async def test_should_return_none_for_missing_brief(
        self, storage: FileSystemStorageAdapter
    ) -> None:
        """get_brief should return None for unknown IDs."""
        assert await storage.get_brief("missing") is None

    @pytest.mark.asyncio
    async def test_should_list_sessions_and_skip_corrupted(
        self, storage: FileSystemStorageAdapter
    ) -> None:
        """list_sessions should return valid sessions and skip corrupted files."""
        session = ChatSession()
        await storage.save_session(session)

        # Write a corrupted JSON file
        corrupted_path = storage._sessions_dir / "corrupted.json"
        corrupted_path.write_text("not json", encoding="utf-8")

        sessions = await storage.list_sessions(limit=10)
        assert len(sessions) == 1
        assert sessions[0].session_id == session.session_id

    @pytest.mark.asyncio
    async def test_should_list_sessions_sorted(self, storage: FileSystemStorageAdapter) -> None:
        """list_sessions should sort by created_at descending."""
        session1 = ChatSession()
        session2 = ChatSession()
        await storage.save_session(session1)
        await storage.save_session(session2)

        sessions = await storage.list_sessions(limit=10)
        assert sessions[0].created_at >= sessions[1].created_at
