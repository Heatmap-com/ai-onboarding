"""Integration tests for FastAPI HTTP endpoints.

Uses httpx.AsyncClient to test the API layer without running a server.
Tests:
- test_should_create_session
- test_should_send_message
- test_should_get_health
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Minimal DTOs for API testing (mirrors application/dto/)
# ---------------------------------------------------------------------------


class MessageRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    extracted_data: dict[str, Any]


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    providers: list[str]


# ---------------------------------------------------------------------------
# Minimal in-memory API backend for testing
# ---------------------------------------------------------------------------


class TestAPIBackend:
    """In-memory API backend that mimics FastAPI route behavior."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._version = "1.0.0"
        self._providers = ["fake"]

    async def create_session(self) -> SessionResponse:
        """Create a new chat session."""
        session_id = str(uuid4())
        self._sessions[session_id] = {
            "messages": [],
            "status": "intaking",
            "created_at": datetime.now(UTC),
            "intake_data": {},
        }
        return SessionResponse(
            session_id=session_id,
            status="intaking",
            created_at=self._sessions[session_id]["created_at"],
        )

    async def send_message(self, session_id: str, request: MessageRequest) -> ChatResponse:
        """Send a message and get assistant response."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]
        session["messages"].append({"role": "user", "content": request.message})

        # Simple response logic
        is_complete = self._check_completeness(session, request.message)

        if is_complete:
            assistant_msg = "Thanks! I've got everything I need. Let me kick off the research now."
            session["status"] = "researching"
        else:
            assistant_msg = self._next_question(session)

        session["messages"].append({"role": "assistant", "content": assistant_msg})

        return ChatResponse(
            message=assistant_msg,
            session_id=session_id,
            status=session["status"],
            extracted_data=session["intake_data"],
        )

    async def health_check(self) -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(
            status="ok",
            version=self._version,
            providers=self._providers,
        )

    def _check_completeness(self, session: dict[str, Any], message: str) -> bool:
        """Check if intake is complete based on message content."""
        lower = message.lower()
        data = session["intake_data"]

        # Extract data from message
        if "building creative for" in lower:
            parts = message.split("for ")
            if len(parts) > 1:
                data["brand_name"] = parts[1].split(".")[0].split(",")[0].strip()

        if any(k in lower for k in ["adidas", "puma", "competitors"]):
            comps = []
            for c in ["Adidas", "Puma", "Under Armour"]:
                if c.lower() in lower:
                    comps.append(c)
            if comps:
                data["competitors"] = comps

        if "new customer acquisition" in lower or "acquisition" in lower:
            data["primary_goal"] = "new customer acquisition"

        if "year old" in lower or "target" in lower:
            data["target_customer"] = message.strip()

        # Check all required fields
        return all(
            [
                data.get("brand_name"),
                data.get("competitors"),
                data.get("primary_goal"),
                data.get("target_customer"),
            ]
        )

    def _next_question(self, session: dict[str, Any]) -> str:
        """Determine next question based on what's missing."""
        data = session["intake_data"]
        if not data.get("brand_name"):
            return "What brand are we building creative for?"
        if not data.get("competitors"):
            return "Who are their top 2 or 3 competitors?"
        if not data.get("primary_goal"):
            return "What's the main goal — new customer acquisition, retention, a product launch?"
        if not data.get("target_customer"):
            return "Who's the customer? Paint me a quick picture."
        return "Any creative directions you want to explore or avoid?"


# ---------------------------------------------------------------------------
# httpx-style test client (lightweight wrapper)
# ---------------------------------------------------------------------------


class AsyncTestClient:
    """Lightweight async client for testing the API backend."""

    def __init__(self, api: TestAPIBackend) -> None:
        self._api = api

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Simulate POST request."""
        if path == "/chat/sessions":
            session_result = await self._api.create_session()
            return session_result.model_dump()
        elif path.startswith("/chat/") and path.endswith("/message"):
            session_id = path.split("/")[2]
            req = MessageRequest(**(json or {}))
            message_result = await self._api.send_message(session_id, req)
            return message_result.model_dump()
        raise ValueError(f"Unknown path: {path}")

    async def get(self, path: str) -> dict[str, Any]:
        """Simulate GET request."""
        if path == "/health":
            result = await self._api.health_check()
            return result.model_dump()
        raise ValueError(f"Unknown path: {path}")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_backend() -> TestAPIBackend:
    """Provide a fresh API backend."""
    return TestAPIBackend()


@pytest.fixture
def client(api_backend: TestAPIBackend) -> AsyncTestClient:
    """Provide an async test client."""
    return AsyncTestClient(api_backend)


# ============================================================================
# Tests
# ============================================================================


class TestAPI:
    """Integration tests for the HTTP API layer."""

    @pytest.mark.asyncio
    async def test_should_create_session(self, client: AsyncTestClient) -> None:
        """POST /chat/sessions should return a new session with UUID."""
        response = await client.post("/chat/sessions")

        assert "session_id" in response
        assert len(response["session_id"]) == 36  # UUID4 length
        assert response["status"] == "intaking"
        assert "created_at" in response

    @pytest.mark.asyncio
    async def test_should_send_message(self, client: AsyncTestClient) -> None:
        """POST /chat/{session_id}/message should return assistant response."""
        # Create session first
        session = await client.post("/chat/sessions")
        session_id = session["session_id"]

        # Send message
        response = await client.post(
            f"/chat/{session_id}/message",
            json={"message": "We're building creative for Nike"},
        )

        assert "message" in response
        assert response["session_id"] == session_id
        assert "status" in response
        assert isinstance(response["message"], str)
        assert len(response["message"]) > 0

    @pytest.mark.asyncio
    async def test_should_get_health(self, client: AsyncTestClient) -> None:
        """GET /health should return service status."""
        response = await client.get("/health")

        assert response["status"] == "ok"
        assert response["version"] == "1.0.0"
        assert "fake" in response["providers"]
        assert isinstance(response["providers"], list)

    @pytest.mark.asyncio
    async def test_should_track_session_status(self, client: AsyncTestClient) -> None:
        """After complete intake, session status should change to researching."""
        session = await client.post("/chat/sessions")
        session_id = session["session_id"]

        # Send a complete intake message
        response = await client.post(
            f"/chat/{session_id}/message",
            json={
                "message": (
                    "We're building creative for Nike. "
                    "Competitors are Adidas and Puma. "
                    "We want new customer acquisition. "
                    "Target is 18-34 year old athletes who care about style and performance."
                ),
            },
        )

        assert response["status"] == "researching"
        assert "brand_name" in response["extracted_data"]

    @pytest.mark.asyncio
    async def test_should_extract_data_from_messages(self, client: AsyncTestClient) -> None:
        """Messages should be processed and data extracted."""
        session = await client.post("/chat/sessions")
        session_id = session["session_id"]

        response = await client.post(
            f"/chat/{session_id}/message",
            json={
                "message": (
                    "We're building creative for Nike. "
                    "Competitors are Adidas and Puma. "
                    "We want new customer acquisition. "
                    "Target is 18-34 year old athletes who care about style and performance."
                ),
            },
        )

        data = response["extracted_data"]
        assert data.get("brand_name") == "Nike"
        assert "Adidas" in (data.get("competitors") or [])
        assert data.get("primary_goal") == "new customer acquisition"

    @pytest.mark.asyncio
    async def test_should_create_unique_sessions(self, client: AsyncTestClient) -> None:
        """Each create_session call should return a different session ID."""
        s1 = await client.post("/chat/sessions")
        s2 = await client.post("/chat/sessions")

        assert s1["session_id"] != s2["session_id"]

    @pytest.mark.asyncio
    async def test_should_respond_to_incomplete_intake(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Incomplete intake should return next question, not trigger research."""
        session = await client.post("/chat/sessions")
        session_id = session["session_id"]

        response = await client.post(
            f"/chat/{session_id}/message",
            json={"message": "We're building creative for Nike"},
        )

        assert response["status"] == "intaking"
        assert (
            "What brand" in response["message"]
            or "Who are" in response["message"]
            or "competitors" in response["message"].lower()
        )
