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

    This is the primary deliverable of Brief Scout. It contains all
    the structured insights needed by creative teams to produce
    effective advertising.
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

    def to_markdown(self) -> str:
        """Render the brief as a professional markdown string.

        Returns:
            A formatted markdown document suitable for display
            in chat interfaces or export to documents.
        """
        lines: list[str] = []

        # Title
        lines.append(f"# Creative Brief: {self.brand_name}")
        lines.append("")

        # Metadata
        lines.append(f"_Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}_")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Brand Positioning
        if self.brand_positioning:
            lines.append("## Brand Positioning")
            lines.append("")
            lines.append(self.brand_positioning)
            lines.append("")

        # Primary Goal
        if self.primary_goal:
            lines.append("## Primary Goal")
            lines.append("")
            lines.append(self.primary_goal)
            lines.append("")

        # Target Customer
        if self.target_customer:
            lines.append("## Target Customer")
            lines.append("")
            lines.append(self.target_customer)
            lines.append("")

        # Customer Desires
        if self.desires:
            lines.append("## Customer Desires")
            lines.append("")
            for desire in self.desires:
                lines.append(f"- {desire}")
            lines.append("")

        # Objections
        if self.objections:
            lines.append("## Objections to Address")
            lines.append("")
            for obj in self.objections:
                lines.append(f"- {obj}")
            lines.append("")

        # Competitive Landscape
        if self.competitive_landscape:
            lines.append("## Competitive Landscape")
            lines.append("")
            lines.append(self.competitive_landscape)
            lines.append("")

        # Creative Angles
        if self.creative_angles:
            lines.append("## Recommended Creative Angles")
            lines.append("")
            for i, angle in enumerate(self.creative_angles, 1):
                lines.append(f"### Angle {i}: {angle.name}")
                lines.append("")
                if angle.description:
                    lines.append(angle.description)
                    lines.append("")
                if angle.rationale:
                    lines.append(f"**Rationale:** {angle.rationale}")
                    lines.append("")

        # Proven Hook Types
        if self.proven_hook_types:
            lines.append("## Proven Hook Types")
            lines.append("")
            for hook in self.proven_hook_types:
                lines.append(f"- {hook}")
            lines.append("")

        # Sample Headlines
        if self.sample_headlines:
            lines.append("## Sample Headlines")
            lines.append("")
            for i, headline in enumerate(self.sample_headlines, 1):
                lines.append(f"{i}. {headline}")
            lines.append("")

        # Creative Mandatories
        has_explore = bool(self.creative_mandatories_explore)
        has_avoid = bool(self.creative_mandatories_avoid)

        if has_explore or has_avoid:
            lines.append("## Creative Mandatories")
            lines.append("")

        if has_explore:
            lines.append("### Explore")
            lines.append("")
            for item in self.creative_mandatories_explore:
                lines.append(f"- {item}")
            lines.append("")

        if has_avoid:
            lines.append("### Avoid")
            lines.append("")
            for item in self.creative_mandatories_avoid:
                lines.append(f"- {item}")
            lines.append("")

        # Category Trends
        if self.category_trends:
            lines.append("## Category Trends")
            lines.append("")
            for trend in self.category_trends:
                lines.append(f"- {trend}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("_Brief Scout | CreativeOS_")
        lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the brief to a dictionary."""
        return self.model_dump()
