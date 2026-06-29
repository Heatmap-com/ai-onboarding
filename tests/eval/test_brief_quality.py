"""Evaluation harness for generated brief quality.

Runs the real application pipeline against known inputs (fixtures) and asserts
that the resulting creative brief is complete, internally consistent, and free
of obvious hallucinations.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from brief_scout.main import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


async def _parse_sse_stream(response: Any) -> list[dict[str, Any]]:
    """Read an SSE stream into a list of event payloads."""
    events: list[dict[str, Any]] = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            payload = json.loads(line.replace("data: ", ""))
            events.append(payload)
    return events


def _without_timestamps(brief: dict[str, Any]) -> dict[str, Any]:
    """Return a brief copy with only timestamp fields removed."""
    copied = dict(brief)
    copied.pop("generated_at", None)
    sources = copied.get("sources")
    if isinstance(sources, dict):
        sources_copy = dict(sources)
        sources_copy.pop("completed_at", None)
        copied["sources"] = sources_copy
    return copied


@pytest.fixture
def app(monkeypatch: Any, tmp_path: Path) -> FastAPI:
    """Create the real FastAPI app pointed at temp data/logs directories."""
    monkeypatch.setenv("BRIEF_SCOUT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BRIEF_SCOUT_TRACK_TOKENS", "false")
    return create_app("config", "test")


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Provide an async HTTP client for the app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def reference_case() -> dict[str, Any]:
    """Load the reference intake/brief case for Nike."""
    case_path = FIXTURES_DIR / "reference_nike_case.yaml"
    if case_path.exists():
        return yaml.safe_load(case_path.read_text(encoding="utf-8"))
    # Default case if the fixture file is not present.
    return {
        "messages": [
            "I'm Alex. We're building creative for Nike",
            "Our competitors are Adidas and Puma",
            "We want new customer acquisition",
            "Our target is 18-34 year old athletes who care about style and performance",
        ],
        "expected_brand_name": "Nike",
        "expected_competitors": ["Adidas", "Puma"],
        "required_fields": [
            "brand_name",
            "brand_positioning",
            "primary_goal",
            "target_customer",
            "creative_angles",
            "sample_headlines",
        ],
        "forbidden_brands": ["Adidas", "Puma"],
    }


class TestBriefQuality:
    """Quality assertions over end-to-end generated briefs."""

    @pytest.mark.asyncio
    async def test_nike_brief_has_required_fields(
        self,
        client: AsyncClient,
        reference_case: dict[str, Any],
    ) -> None:
        """A known complete intake should produce a brief with all required fields."""
        session_resp = await client.post("/api/v1/chat/sessions")
        session_id = session_resp.json()["session_id"]

        messages: list[str] = reference_case["messages"]
        # Send the first messages as normal JSON; the final message triggers the
        # SSE pipeline stream.
        for message in messages[:-1]:
            resp = await client.post(
                f"/api/v1/chat/{session_id}/message",
                json={"message": message},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == session_id

        async with client.stream(
            "POST",
            f"/api/v1/chat/{session_id}/message",
            json={"message": messages[-1]},
            timeout=30,
        ) as response:
            assert response.status_code == 200
            events = await _parse_sse_stream(response)

        brief_event = next((e for e in events if e.get("type") == "brief"), None)
        assert brief_event is not None, "Pipeline should emit a brief event"
        brief = brief_event["brief"]

        for field in reference_case["required_fields"]:
            assert brief.get(field), f"Required field '{field}' is missing or empty"

    @pytest.mark.asyncio
    async def test_nike_brief_matches_input_brand(
        self,
        client: AsyncClient,
        reference_case: dict[str, Any],
    ) -> None:
        """The generated brief should reflect the input brand, not hallucinate one."""
        session_resp = await client.post("/api/v1/chat/sessions")
        session_id = session_resp.json()["session_id"]

        messages: list[str] = reference_case["messages"]
        for message in messages[:-1]:
            await client.post(
                f"/api/v1/chat/{session_id}/message",
                json={"message": message},
            )

        async with client.stream(
            "POST",
            f"/api/v1/chat/{session_id}/message",
            json={"message": messages[-1]},
            timeout=30,
        ) as response:
            events = await _parse_sse_stream(response)

        brief_event = next((e for e in events if e.get("type") == "brief"), None)
        assert brief_event is not None
        brief = brief_event["brief"]

        assert brief["brand_name"] == reference_case["expected_brand_name"]
        markdown: str = brief_event["markdown"]
        assert reference_case["expected_brand_name"] in markdown

    @pytest.mark.asyncio
    async def test_creative_angles_are_substantial(
        self,
        client: AsyncClient,
        reference_case: dict[str, Any],
    ) -> None:
        """Creative angles should have names and descriptions."""
        session_resp = await client.post("/api/v1/chat/sessions")
        session_id = session_resp.json()["session_id"]

        messages: list[str] = reference_case["messages"]
        for message in messages[:-1]:
            await client.post(
                f"/api/v1/chat/{session_id}/message",
                json={"message": message},
            )

        async with client.stream(
            "POST",
            f"/api/v1/chat/{session_id}/message",
            json={"message": messages[-1]},
            timeout=30,
        ) as response:
            events = await _parse_sse_stream(response)

        brief_event = next((e for e in events if e.get("type") == "brief"), None)
        assert brief_event is not None
        brief = brief_event["brief"]

        angles: list[dict[str, Any]] = brief["creative_angles"]
        assert len(angles) >= 1, "Brief should contain at least one creative angle"
        for angle in angles:
            assert angle.get("name"), "Creative angle is missing a name"
            assert angle.get("description"), "Creative angle is missing a description"

    @pytest.mark.asyncio
    async def test_brief_idempotent_across_runs(
        self,
        client: AsyncClient,
        reference_case: dict[str, Any],
    ) -> None:
        """Two identical intake conversations should produce identical briefs."""
        briefs: list[dict[str, Any]] = []

        for _ in range(2):
            session_resp = await client.post("/api/v1/chat/sessions")
            session_id = session_resp.json()["session_id"]

            messages: list[str] = reference_case["messages"]
            for message in messages[:-1]:
                await client.post(
                    f"/api/v1/chat/{session_id}/message",
                    json={"message": message},
                )

            async with client.stream(
                "POST",
                f"/api/v1/chat/{session_id}/message",
                json={"message": messages[-1]},
                timeout=30,
            ) as response:
                events = await _parse_sse_stream(response)

            brief_event = next((e for e in events if e.get("type") == "brief"), None)
            assert brief_event is not None
            briefs.append(brief_event["brief"])

        stripped = [_without_timestamps(b) for b in briefs]
        assert stripped[0] == stripped[1], "Identical inputs should produce identical briefs"
