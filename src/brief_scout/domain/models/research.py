"""Research result models for the parallel research calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T", bound=BaseModel)


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


_KNOWN_RESULT_KEYS: dict[str, type[BaseModel]] = {
    "brand_audit": BrandAuditResult,
    "competitor_scan": CompetitorScanResult,
    "trend_pulse": TrendPulseResult,
    "customer_voice": CustomerVoiceResult,
    "hook_mining": HookMiningResult,
}


class ResearchBundle(BaseModel):
    """Aggregated results from all research calls.

    Results are stored in an open ``results`` dictionary keyed by step name.
    Typed accessors are provided for the five built-in research steps so
    existing callers can keep using ``bundle.brand_audit`` style access.

    ``model_dump()`` flattens the results dictionary so the JSON shape
    remains backward-compatible (``brand_audit``, ``completed_at``, etc.).
    """

    model_config = ConfigDict(frozen=False, extra="allow")

    results: dict[str, BaseModel] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def __init__(self, **data: Any) -> None:
        """Accept legacy typed field kwargs for backward compatibility."""
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """Move legacy typed fields into the open ``results`` dictionary."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        results = data.get("results", {})
        if not isinstance(results, dict):
            results = {}
        for key in list(_KNOWN_RESULT_KEYS):
            if key in data and key not in results:
                results[key] = data.pop(key)
        data["results"] = results
        return data

    def _get_result(self, key: str, schema: type[T]) -> T:
        """Return a typed result, defaulting to an empty instance."""
        result = self.results.get(key)
        if isinstance(result, schema):
            return result
        return schema()

    def _set_result(self, key: str, value: BaseModel) -> None:
        """Store a result under its step name."""
        self.results[key] = value

    @property
    def brand_audit(self) -> BrandAuditResult:
        """Brand audit result."""
        return self._get_result("brand_audit", BrandAuditResult)

    @brand_audit.setter
    def brand_audit(self, value: BrandAuditResult) -> None:
        self._set_result("brand_audit", value)

    @property
    def competitor_scan(self) -> CompetitorScanResult:
        """Competitor scan result."""
        return self._get_result("competitor_scan", CompetitorScanResult)

    @competitor_scan.setter
    def competitor_scan(self, value: CompetitorScanResult) -> None:
        self._set_result("competitor_scan", value)

    @property
    def trend_pulse(self) -> TrendPulseResult:
        """Trend pulse result."""
        return self._get_result("trend_pulse", TrendPulseResult)

    @trend_pulse.setter
    def trend_pulse(self, value: TrendPulseResult) -> None:
        self._set_result("trend_pulse", value)

    @property
    def customer_voice(self) -> CustomerVoiceResult:
        """Customer voice result."""
        return self._get_result("customer_voice", CustomerVoiceResult)

    @customer_voice.setter
    def customer_voice(self, value: CustomerVoiceResult) -> None:
        self._set_result("customer_voice", value)

    @property
    def hook_mining(self) -> HookMiningResult:
        """Hook mining result."""
        return self._get_result("hook_mining", HookMiningResult)

    @hook_mining.setter
    def hook_mining(self, value: HookMiningResult) -> None:
        self._set_result("hook_mining", value)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Flatten results for backward-compatible serialization."""
        flattened: dict[str, Any] = {
            name: result.model_dump(**kwargs) for name, result in self.results.items()
        }
        flattened["completed_at"] = self.completed_at
        return flattened

    def model_dump_json(self, **kwargs: Any) -> str:
        """Serialize using the flattened ``model_dump`` representation."""
        from pydantic import TypeAdapter

        return TypeAdapter(dict[str, Any]).dump_json(self.model_dump(**kwargs)).decode()
