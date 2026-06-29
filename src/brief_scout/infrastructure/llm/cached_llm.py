"""SQLite-backed LLM response cache.

Caches exact prompt/model/temperature responses so duplicate provider calls
can be served from a local SQLite database instead of the network. Implements
``LLMPort`` so it can wrap any adapter transparently.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from typing import TYPE_CHECKING, Any, cast

from brief_scout.domain.models.config import LLMCacheConfig
from brief_scout.domain.ports.llm_port import LLMResponse

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import Prompt, T


class CachedLLM:
    """Decorator that caches LLM responses in SQLite.

    The cache key covers the provider, model, prompt contents, structured
    output schema name, and call config so that only truly identical calls
    hit the cache.

    Args:
        adapter: The underlying LLM adapter to wrap.
        model: Model name used in cache keys and metadata.
        config: Cache configuration (path, TTL, max entries).
    """

    def __init__(
        self,
        adapter: Any,
        model: str = "",
        config: LLMCacheConfig | None = None,
    ) -> None:
        """Initialize the cache and ensure the database schema exists."""
        self._adapter = adapter
        self._model = model or getattr(adapter, "model", "") or "unknown"
        self._config = config or LLMCacheConfig()
        self._provider = getattr(adapter, "provider_name", "unknown")
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._connection: sqlite3.Connection | None = None
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create the database directory, connection, and table."""
        db_dir = os.path.dirname(self._config.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self._config.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                output_schema TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
            """,
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_last_accessed ON llm_cache(last_accessed);",
        )
        conn.commit()
        self._connection = conn

    @property
    def provider_name(self) -> str:
        """Return the underlying provider identifier."""
        return self._provider

    @property
    def stats(self) -> dict[str, int]:
        """Return cache statistics including current size."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": self._size(),
        }

    def _size(self) -> int:
        """Return the number of entries currently in the cache."""
        if self._connection is None:
            return 0
        cur = self._connection.execute("SELECT COUNT(*) FROM llm_cache")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def _cache_key(
        self,
        prompt: Prompt,
        output_schema: str,
        config: dict[str, Any] | None,
    ) -> str:
        """Build a deterministic cache key for a call."""
        canonical = json.dumps(
            {
                "provider": self._provider,
                "model": self._model,
                "system": prompt.system,
                "user": prompt.user,
                "context": [message.model_dump() for message in prompt.context],
                "schema": output_schema,
                "config": config or {},
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Return a cached completion or delegate to the adapter."""
        key = self._cache_key(prompt, "", config)
        cached = await self._get_response(key)
        if cached is not None:
            self._hits += 1
            return LLMResponse.model_validate_json(cached)

        response = cast("LLMResponse", await self._adapter.complete(prompt, config))
        await self._store_response(key, "", response.model_dump_json())
        self._misses += 1
        return response

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Return a cached structured result or delegate to the adapter."""
        key = self._cache_key(prompt, output_schema.__name__, config)
        cached = await self._get_response(key)
        if cached is not None:
            self._hits += 1
            return output_schema.model_validate_json(cached)

        result = cast(
            "T",
            await self._adapter.complete_structured(
                prompt,
                output_schema,
                config,
            ),
        )
        await self._store_response(key, output_schema.__name__, result.model_dump_json())
        self._misses += 1
        return result

    async def _get_response(self, key: str) -> str | None:
        """Fetch a cached response under the global lock."""
        async with self._lock:
            return await asyncio.to_thread(self._get_response_sync, key)

    def _get_response_sync(self, key: str) -> str | None:
        """Synchronously fetch and validate a cached response."""
        if self._connection is None:
            return None

        cur = self._connection.execute(
            "SELECT response_json, expires_at FROM llm_cache WHERE key = ?",
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        response_json: str = row[0]
        expires_at: float = row[1]
        now = time.time()
        if expires_at and now > expires_at:
            self._connection.execute(
                "DELETE FROM llm_cache WHERE key = ?",
                (key,),
            )
            self._connection.commit()
            return None

        self._connection.execute(
            "UPDATE llm_cache SET last_accessed = ? WHERE key = ?",
            (now, key),
        )
        self._connection.commit()
        return response_json

    async def _store_response(
        self,
        key: str,
        output_schema: str,
        response_json: str,
    ) -> None:
        """Persist a response under the global lock."""
        async with self._lock:
            await asyncio.to_thread(
                self._store_response_sync,
                key,
                output_schema,
                response_json,
            )

    def _store_response_sync(
        self,
        key: str,
        output_schema: str,
        response_json: str,
    ) -> None:
        """Synchronously insert a response and enforce the size cap."""
        if self._connection is None:
            return

        now = time.time()
        expires_at = 0.0
        if self._config.ttl_seconds > 0:
            expires_at = now + self._config.ttl_seconds

        self._connection.execute(
            """
            INSERT OR REPLACE INTO llm_cache
            (key, provider, model, output_schema, response_json, created_at, expires_at, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                self._provider,
                self._model,
                output_schema,
                response_json,
                now,
                expires_at,
                now,
            ),
        )

        if self._config.max_entries > 0:
            total = self._size()
            if total > self._config.max_entries:
                overage = total - self._config.max_entries
                self._connection.execute(
                    """
                    DELETE FROM llm_cache
                    WHERE key IN (
                        SELECT key FROM llm_cache ORDER BY last_accessed ASC LIMIT ?
                    )
                    """,
                    (overage,),
                )

        self._connection.commit()

    async def clear(self) -> None:
        """Remove all cached entries."""
        async with self._lock:
            await asyncio.to_thread(self._clear_sync)

    def _clear_sync(self) -> None:
        """Synchronously clear the cache table."""
        if self._connection is not None:
            self._connection.execute("DELETE FROM llm_cache")
            self._connection.commit()

    async def close(self) -> None:
        """Close the SQLite connection."""
        async with self._lock:
            if self._connection is not None:
                await asyncio.to_thread(self._connection.close)
                self._connection = None
