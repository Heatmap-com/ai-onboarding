"""Intake data models for conversational brief collection."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    """Pipeline status for a chat session."""

    INTAKING = "intaking"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


class CreativeDirections(BaseModel):
    """Creative direction preferences from the intake conversation."""

    model_config = ConfigDict(frozen=False)

    explore: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class IntakeData(BaseModel):
    """Structured data collected during conversational intake.

    Required fields for research trigger are defined by the intake journey
    schema (see ``IntakeJourney``). This model is intentionally a plain data
    container; completeness evaluation lives in ``CompletenessChecker``.
    """

    model_config = ConfigDict(frozen=False)

    first_name: str = ""
    brand_name: str = ""
    brand_url: str = ""
    competitors: list[str] = Field(default_factory=list)
    primary_goal: str = ""
    target_customer: str = ""
    creative_directions: CreativeDirections = Field(default_factory=CreativeDirections)
    additional_context: str = ""

    def is_complete(self) -> bool:
        """Return True when all required intake fields are populated."""
        return bool(
            self.brand_name and self.competitors and self.primary_goal and self.target_customer
        )


class ChatMessage(BaseModel):
    """A single message in the chat conversation."""

    model_config = ConfigDict(frozen=False)

    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatSession(BaseModel):
    """Full chat session tracking state and conversation history."""

    model_config = ConfigDict(frozen=False)

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[ChatMessage] = Field(default_factory=list)
    intake_data: IntakeData = Field(default_factory=IntakeData)
    asked_optional_questions: list[str] = Field(default_factory=list)
    status: Status = Status.INTAKING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
