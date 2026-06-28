"""Research result models for the five parallel research calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BrandAuditResult(BaseModel):
    """Call 1 — Brand Audit.

    Analyzes the brand's positioning, creative angles, messaging,
    visual identity, and recent campaign activity.
    """

    model_config = ConfigDict(frozen=False)

    brand_positioning: str = ""
    current_creative_angle: str = ""
    key_messages: list[str] = Field(default_factory=list)
    visual_identity_notes: str = ""
    recent_campaigns: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return self.model_dump()


class CompetitorData(BaseModel):
    """Data about a single competitor from the competitor scan."""

    model_config = ConfigDict(frozen=False)

    name: str = ""
    primary_creative_angle: str = ""
    key_messages: list[str] = Field(default_factory=list)
    apparent_target_audience: str = ""
    creative_gaps: str = ""


class CompetitorScanResult(BaseModel):
    """Call 2 — Competitor Ad Scan.

    Analyzes competitor advertising strategies, creative patterns,
    and identifies whitespace opportunities.
    """

    model_config = ConfigDict(frozen=False)

    competitors: list[CompetitorData] = Field(default_factory=list)
    category_creative_patterns: str = ""
    whitespace_opportunities: list[str] = Field(default_factory=list)


class TrendPulseResult(BaseModel):
    """Call 3 — Category & Trend Pulse.

    Identifies category trends, cultural moments, emerging angles,
    and timing considerations.
    """

    model_config = ConfigDict(frozen=False)

    category_trends: list[str] = Field(default_factory=list)
    cultural_moments: list[str] = Field(default_factory=list)
    emerging_angles: list[str] = Field(default_factory=list)
    timing_notes: str = ""


class CustomerVoiceResult(BaseModel):
    """Call 4 — Customer Voice.

    Captures customer language, desires, frustrations, emotional
    drivers, and objections.
    """

    model_config = ConfigDict(frozen=False)

    customer_language: list[str] = Field(default_factory=list)
    top_desires: list[str] = Field(default_factory=list)
    top_frustrations: list[str] = Field(default_factory=list)
    emotional_drivers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)


class HookMiningResult(BaseModel):
    """Call 5 — Hook & Angle Mining.

    Identifies proven hook types, emotional and rational angles,
    format recommendations, and headline starters.
    """

    model_config = ConfigDict(frozen=False)

    proven_hook_types: list[str] = Field(default_factory=list)
    emotional_angles: list[str] = Field(default_factory=list)
    rational_angles: list[str] = Field(default_factory=list)
    format_recommendations: list[str] = Field(default_factory=list)
    headline_starters: list[str] = Field(default_factory=list)


class ResearchBundle(BaseModel):
    """Aggregated results from all 5 research calls.

    Contains the complete output of the research phase, ready
    for synthesis into a Brief.
    """

    model_config = ConfigDict(frozen=False)

    brand_audit: BrandAuditResult = Field(default_factory=BrandAuditResult)
    competitor_scan: CompetitorScanResult = Field(default_factory=CompetitorScanResult)
    trend_pulse: TrendPulseResult = Field(default_factory=TrendPulseResult)
    customer_voice: CustomerVoiceResult = Field(default_factory=CustomerVoiceResult)
    hook_mining: HookMiningResult = Field(default_factory=HookMiningResult)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
