"""Unit tests for the SQLite-backed LLM response cache."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from brief_scout.domain.ports.llm_port import LLMResponse, Prompt
from brief_scout.infrastructure.llm.cached_llm import CachedLLM, LLMCacheConfig


class _Greeting(BaseModel):
    """Tiny model for structured-output cache tests."""

    message: str = ""


class _MockAdapter:
    """Deterministic mock LLM adapter with call counters."""

    provider_name = "mock"
    model = "mock-model"

    def __init__(self) -> None:
        self.complete_calls = 0
        self.structured_calls = 0

    async def complete(
        self,
        _prompt: Prompt,
        _config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Return a fresh completion and count the call."""
        self.complete_calls += 1
        return LLMResponse(
            content="hello",
            model_used="mock-model",
            provider="mock",
            tokens_used=1,
            latency_ms=1.0,
            finish_reason="stop",
            metadata={"call": self.complete_calls},
        )

    async def complete_structured(
        self,
        _prompt: Prompt,
        _output_schema: type[_Greeting],
        _config: dict[str, Any] | None = None,
    ) -> _Greeting:
        """Return a fresh structured result and count the call."""
        self.structured_calls += 1
        return _Greeting(message=f"structured {self.structured_calls}")


@pytest.fixture
def mock_adapter() -> _MockAdapter:
    """Provide a fresh mock adapter."""
    return _MockAdapter()


@pytest.fixture
def cache_config(tmp_path: Any) -> LLMCacheConfig:
    """Provide a cache config that writes to a temporary database."""
    return LLMCacheConfig(
        enabled=True,
        db_path=str(tmp_path / "llm_cache.db"),
        ttl_seconds=3600,
        max_entries=100,
    )


@pytest.mark.asyncio
async def test_complete_cache_hit_avoids_adapter_call(
    mock_adapter: _MockAdapter,
    cache_config: LLMCacheConfig,
) -> None:
    """A second identical completion should be served from the cache."""
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=cache_config)
    prompt = Prompt(system="sys", user="user")

    first = await cached.complete(prompt)
    second = await cached.complete(prompt)

    assert mock_adapter.complete_calls == 1
    assert first.content == second.content
    assert first.model_used == second.model_used
    assert cached.stats["hits"] == 1
    assert cached.stats["misses"] == 1
    assert cached.stats["size"] == 1


@pytest.mark.asyncio
async def test_complete_different_prompts_are_cached_separately(
    mock_adapter: _MockAdapter,
    cache_config: LLMCacheConfig,
) -> None:
    """Different prompts should produce distinct cache entries."""
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=cache_config)

    await cached.complete(Prompt(system="sys", user="one"))
    await cached.complete(Prompt(system="sys", user="two"))

    assert mock_adapter.complete_calls == 2
    assert cached.stats["size"] == 2


@pytest.mark.asyncio
async def test_complete_structured_cache_hit(
    mock_adapter: _MockAdapter,
    cache_config: LLMCacheConfig,
) -> None:
    """A second identical structured call should be served from the cache."""
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=cache_config)
    prompt = Prompt(system="sys", user=" structured")

    first = await cached.complete_structured(prompt, _Greeting)
    second = await cached.complete_structured(prompt, _Greeting)

    assert mock_adapter.structured_calls == 1
    assert first.message == second.message
    assert cached.stats["hits"] == 1
    assert cached.stats["misses"] == 1


@pytest.mark.asyncio
async def test_cache_respects_ttl(
    mock_adapter: _MockAdapter,
    tmp_path: Any,
) -> None:
    """Entries older than the TTL are treated as cache misses."""
    db_path = tmp_path / "llm_cache.db"
    config = LLMCacheConfig(
        enabled=True,
        db_path=str(db_path),
        ttl_seconds=1,
        max_entries=100,
    )
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=config)
    prompt = Prompt(system="sys", user="ttl")

    await cached.complete(prompt)
    assert cached.stats["size"] == 1
    assert cached.stats["misses"] == 1

    await asyncio.sleep(1.1)

    # Re-open the same database to verify TTL is enforced on load.
    cached2 = CachedLLM(adapter=mock_adapter, model="mock-model", config=config)
    await cached2.complete(prompt)

    assert mock_adapter.complete_calls == 2
    assert cached2.stats["misses"] == 1
    assert cached2.stats["hits"] == 0


@pytest.mark.asyncio
async def test_cache_enforces_max_entries(
    mock_adapter: _MockAdapter,
    tmp_path: Any,
) -> None:
    """When the cache exceeds max_entries, the oldest entries are evicted."""
    config = LLMCacheConfig(
        enabled=True,
        db_path=str(tmp_path / "llm_cache.db"),
        ttl_seconds=3600,
        max_entries=2,
    )
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=config)

    await cached.complete(Prompt(system="sys", user="first"))
    await cached.complete(Prompt(system="sys", user="second"))
    await cached.complete(Prompt(system="sys", user="third"))

    assert cached.stats["size"] == 2
    assert mock_adapter.complete_calls == 3

    # The oldest entry should have been evicted.
    await cached.complete(Prompt(system="sys", user="first"))
    assert mock_adapter.complete_calls == 4
    assert cached.stats["misses"] == 4


@pytest.mark.asyncio
async def test_cache_clear_removes_all_entries(
    mock_adapter: _MockAdapter,
    cache_config: LLMCacheConfig,
) -> None:
    """Clear should drop every cached entry."""
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=cache_config)
    await cached.complete(Prompt(system="sys", user="clear me"))
    assert cached.stats["size"] == 1

    await cached.clear()

    assert cached.stats["size"] == 0
    # After clearing, the next call should miss and re-invoke the adapter.
    await cached.complete(Prompt(system="sys", user="clear me"))
    assert mock_adapter.complete_calls == 2


@pytest.mark.asyncio
async def test_cache_close_does_not_break_pass_through(
    mock_adapter: _MockAdapter,
    cache_config: LLMCacheConfig,
) -> None:
    """After close, the cache should transparently delegate to the adapter."""
    cached = CachedLLM(adapter=mock_adapter, model="mock-model", config=cache_config)
    await cached.close()

    result = await cached.complete(Prompt(system="sys", user="after close"))
    assert result.content == "hello"
    assert mock_adapter.complete_calls == 1
