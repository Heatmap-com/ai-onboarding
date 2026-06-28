"""Data Transfer Objects for the intake/chat flow.

Per SPEC 10 — Defines request/response models for chat session management
and message exchange between the interface and application layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from brief_scout.domain.models.intake import Status


class MessageRequest(BaseModel):
    """Request body for sending a chat message.

    Attributes:
        message: The user's message text.
        session_id: Optional session ID for continuing a conversation.
    """

    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response for a single chat message exchange.

    Attributes:
        message: The assistant's reply text.
        session_id: The session identifier.
        status: Current pipeline status.
        extracted_data: Structured data extracted from the conversation so far.
    """

    message: str
    session_id: str
    status: Status = Status.INTAKING
    extracted_data: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    """Response for session creation.

    Attributes:
        session_id: The unique session identifier.
        status: Initial session status.
        created_at: Timestamp when the session was created.
    """

    session_id: str
    status: Status = Status.INTAKING
    created_at: datetime
