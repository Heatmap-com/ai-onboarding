"""Brief model — the final creative brief output."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from brief_scout.domain.models.research import ResearchBundle


class CreativeAngle(BaseModel):
    """A recommended creative angle with rationale."""

    model_config = ConfigDict(frozen=False)

    name: str = ""
    description: str = ""
    rationale: str = ""


class BriefSection(BaseModel):
    """Generic section within a brief."""

    model_config = ConfigDict(frozen=False)

    title: str = ""
    content: str = ""
    bullets: list[str] = Field(default_factory=list)


class Brief(BaseModel):
    """Complete creative brief — final output of the synthesis pipeline.

    This is a pure data model. Markdown rendering lives in
    ``brief_scout.application.services.brief_markdown_renderer``.
    """

    model_config = ConfigDict(frozen=False)

    brand_name: str = ""
    brand_positioning: str = ""
    primary_goal: str = ""
    target_customer: str = ""
    desires: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    competitive_landscape: str = ""
    creative_angles: list[CreativeAngle] = Field(default_factory=list)
    proven_hook_types: list[str] = Field(default_factory=list)
    sample_headlines: list[str] = Field(default_factory=list)
    creative_mandatories_explore: list[str] = Field(default_factory=list)
    creative_mandatories_avoid: list[str] = Field(default_factory=list)
    category_trends: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sources: ResearchBundle = Field(default_factory=ResearchBundle)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the brief to a dictionary."""
        return self.model_dump()
