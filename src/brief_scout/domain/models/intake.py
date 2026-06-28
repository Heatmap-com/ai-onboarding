"""Intake data models for conversational brief collection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CreativeDirections(BaseModel):
    """Creative direction preferences from the intake conversation."""

    model_config = ConfigDict(frozen=False)

    explore: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class IntakeData(BaseModel):
    """Structured data collected during conversational intake.

    Required fields for research trigger: brand_name, competitors (>=1),
    primary_goal, target_customer.
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

    @property
    def is_complete(self) -> bool:
        """Check if the original four required fields are populated.

        This is a convenience helper for tests and backward compatibility.
        The authoritative completeness check is performed by the journey-driven
        CompletenessChecker, which may include additional required fields such
        as ``first_name``.
        """
        return bool(
            self.brand_name.strip()
            and len(self.competitors) >= 1
            and self.primary_goal.strip()
            and self.target_customer.strip()
        )

    @property
    def completion_score(self) -> float:
        """Return 0.0 to 1.0 indicating what fraction of all fields are filled."""
        fields = [
            self.first_name,
            self.brand_name,
            self.brand_url,
            self.competitors,
            self.primary_goal,
            self.target_customer,
            self.additional_context,
        ]
        dirs = self.creative_directions
        fields.extend([dirs.explore, dirs.avoid])
        filled = sum(1 for f in fields if f)
        return filled / len(fields)


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
    status: Literal["intaking", "researching", "synthesizing", "complete"] = "intaking"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
