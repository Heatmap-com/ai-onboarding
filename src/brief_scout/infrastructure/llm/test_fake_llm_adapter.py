"""Test-only Fake LLM adapter with call-log helpers.

Production code should use ``FakeLLMAdapter``. Tests that need to inspect
or reset recorded calls should use this subclass.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from brief_scout.infrastructure.llm.fake_llm_adapter import FakeLLMAdapter

if TYPE_CHECKING:
    from brief_scout.domain.ports.llm_port import LLMResponse, Prompt


class TestFakeLLMAdapter(FakeLLMAdapter):
    """Fake LLM adapter that records calls for test verification."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the test adapter with an empty call log."""
        super().__init__(*args, **kwargs)
        self._call_log: list[dict[str, Any]] = []

    async def complete(
        self,
        prompt: Prompt,
        config: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Return a fixture-based response and record the call."""
        response = await super().complete(prompt, config)

        call_record = {
            "fixture_name": response.metadata.get("provider_metadata", {}).get(
                "fixture_name", "unknown"
            ),
            "prompt_user": prompt.user[:500],
            "prompt_system": prompt.system[:500],
            "response_content": response.content[:1000],
            "latency_ms": response.latency_ms,
            "timestamp": asyncio.get_event_loop().time(),
        }
        self._call_log.append(call_record)

        return response

    def get_call_log(self) -> list[dict[str, Any]]:
        """Return all recorded calls for test verification."""
        return list(self._call_log)

    def clear_call_log(self) -> None:
        """Clear the call log between tests."""
        self._call_log.clear()
