"""Markdown renderer for the ``Brief`` domain model.

This service owns presentation formatting so that ``Brief`` can remain a
pure data model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brief_scout.domain.models.brief import Brief


class BriefMarkdownRenderer:
    """Renders a ``Brief`` as a professional markdown document."""

    def render(self, brief: Brief) -> str:
        """Return the brief formatted as markdown."""
        lines: list[str] = []

        # Title
        lines.append(f"# Creative Brief: {brief.brand_name}")
        lines.append("")

        # Metadata
        lines.append(f"_Generated: {brief.generated_at.strftime('%Y-%m-%d %H:%M UTC')}_")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Brand Positioning
        if brief.brand_positioning:
            lines.append("## Brand Positioning")
            lines.append("")
            lines.append(brief.brand_positioning)
            lines.append("")

        # Primary Goal
        if brief.primary_goal:
            lines.append("## Primary Goal")
            lines.append("")
            lines.append(brief.primary_goal)
            lines.append("")

        # Target Customer
        if brief.target_customer:
            lines.append("## Target Customer")
            lines.append("")
            lines.append(brief.target_customer)
            lines.append("")

        # Customer Desires
        if brief.desires:
            lines.append("## Customer Desires")
            lines.append("")
            for desire in brief.desires:
                lines.append(f"- {desire}")
            lines.append("")

        # Objections
        if brief.objections:
            lines.append("## Objections to Address")
            lines.append("")
            for obj in brief.objections:
                lines.append(f"- {obj}")
            lines.append("")

        # Competitive Landscape
        if brief.competitive_landscape:
            lines.append("## Competitive Landscape")
            lines.append("")
            lines.append(brief.competitive_landscape)
            lines.append("")

        # Creative Angles
        if brief.creative_angles:
            lines.append("## Recommended Creative Angles")
            lines.append("")
            for i, angle in enumerate(brief.creative_angles, 1):
                lines.append(f"### Angle {i}: {angle.name}")
                lines.append("")
                if angle.description:
                    lines.append(angle.description)
                    lines.append("")
                if angle.rationale:
                    lines.append(f"**Rationale:** {angle.rationale}")
                    lines.append("")

        # Proven Hook Types
        if brief.proven_hook_types:
            lines.append("## Proven Hook Types")
            lines.append("")
            for hook in brief.proven_hook_types:
                lines.append(f"- {hook}")
            lines.append("")

        # Sample Headlines
        if brief.sample_headlines:
            lines.append("## Sample Headlines")
            lines.append("")
            for i, headline in enumerate(brief.sample_headlines, 1):
                lines.append(f"{i}. {headline}")
            lines.append("")

        # Creative Mandatories
        has_explore = bool(brief.creative_mandatories_explore)
        has_avoid = bool(brief.creative_mandatories_avoid)

        if has_explore or has_avoid:
            lines.append("## Creative Mandatories")
            lines.append("")

        if has_explore:
            lines.append("### Explore")
            lines.append("")
            for item in brief.creative_mandatories_explore:
                lines.append(f"- {item}")
            lines.append("")

        if has_avoid:
            lines.append("### Avoid")
            lines.append("")
            for item in brief.creative_mandatories_avoid:
                lines.append(f"- {item}")
            lines.append("")

        # Category Trends
        if brief.category_trends:
            lines.append("## Category Trends")
            lines.append("")
            for trend in brief.category_trends:
                lines.append(f"- {trend}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("_Brief Scout | CreativeOS_")
        lines.append("")

        return "\n".join(lines)
