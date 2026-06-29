"""Comprehensive unit tests for domain models.

Covers IntakeData, ChatSession, Brief, ResearchBundle, and CreativeDirections.
Target: 95% coverage.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from brief_scout.application.services.brief_markdown_renderer import BriefMarkdownRenderer
from brief_scout.domain.models.brief import Brief, BriefSection, CreativeAngle
from brief_scout.domain.models.intake import (
    ChatMessage,
    ChatSession,
    CreativeDirections,
    IntakeData,
    Status,
)
from brief_scout.domain.models.research import (
    BrandAuditResult,
    CompetitorData,
    CompetitorScanResult,
    CustomerVoiceResult,
    HookMiningResult,
    ResearchBundle,
    TrendPulseResult,
)

# ============================================================================
# TestIntakeData
# ============================================================================


class TestIntakeData:
    """Test the IntakeData model — defaults and field behavior."""

    def test_default_construction(self) -> None:
        """Default construction yields empty strings and empty lists."""
        data = IntakeData()
        assert data.first_name == ""
        assert data.brand_name == ""
        assert data.brand_url == ""
        assert data.competitors == []
        assert data.primary_goal == ""
        assert data.target_customer == ""
        assert isinstance(data.creative_directions, CreativeDirections)
        assert data.additional_context == ""

    def test_field_assignment(self) -> None:
        """Fields can be assigned after construction."""
        data = IntakeData()
        data.brand_name = "Nike"
        assert data.brand_name == "Nike"

    def test_competitors_is_list(self) -> None:
        """competitors must be a list of strings."""
        data = IntakeData(competitors=["Adidas", "Puma"])
        assert len(data.competitors) == 2
        assert all(isinstance(c, str) for c in data.competitors)


# ============================================================================
# TestChatSession
# ============================================================================


class TestChatSession:
    """Test the ChatSession model — ID generation, defaults, message handling."""

    def test_default_creation(self) -> None:
        """Default ChatSession has UUID id, empty messages, default status."""
        session = ChatSession()
        assert session.session_id
        assert isinstance(session.session_id, str)
        assert session.messages == []
        assert session.status == "intaking"
        assert isinstance(session.created_at, datetime)

    def test_session_id_is_uuid(self) -> None:
        """session_id should be a valid UUID4 string."""
        session = ChatSession()
        # Should not raise
        parsed = UUID(session.session_id)
        assert parsed.version == 4

    def test_intake_data_default(self) -> None:
        """ChatSession carries default IntakeData."""
        session = ChatSession()
        assert isinstance(session.intake_data, IntakeData)
        assert session.intake_data.brand_name == ""

    def test_adding_messages(self) -> None:
        """Messages can be appended to the session."""
        session = ChatSession()
        msg = ChatMessage(role="user", content="Hello")
        session.messages.append(msg)
        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"

    def test_status_transition(self) -> None:
        """Status can be transitioned through pipeline phases."""
        session = ChatSession()
        assert session.status == Status.INTAKING
        session.status = Status.RESEARCHING
        assert session.status == Status.RESEARCHING
        session.status = Status.SYNTHESIZING
        assert session.status == Status.SYNTHESIZING
        session.status = Status.COMPLETE
        assert session.status == Status.COMPLETE


class TestStatus:
    """Test the Status enum."""

    def test_status_values(self) -> None:
        """Status enum values match the expected strings."""
        assert Status.INTAKING == "intaking"
        assert Status.RESEARCHING == "researching"
        assert Status.SYNTHESIZING == "synthesizing"
        assert Status.COMPLETE == "complete"

    def test_status_serialization(self) -> None:
        """Status serializes as its string value."""
        assert Status.RESEARCHING.value == "researching"

    def test_unique_sessions(self) -> None:
        """Each session gets a unique session_id."""
        s1 = ChatSession()
        s2 = ChatSession()
        assert s1.session_id != s2.session_id


# ============================================================================
# TestBrief
# ============================================================================


class TestBrief:
    """Test the Brief model — markdown rendering, field access, construction."""

    def test_to_markdown_contains_brand(self) -> None:
        """Markdown output contains the brand name."""
        brief = Brief(brand_name="Nike")
        md = BriefMarkdownRenderer().render(brief)
        assert "Nike" in md
        assert "# Creative Brief: Nike" in md

    def test_to_markdown_has_all_sections(self) -> None:
        """Markdown output contains all expected section headers."""
        brief = Brief(
            brand_name="Nike",
            brand_positioning="The ultimate performance brand.",
            primary_goal="new customer acquisition",
            target_customer="18-34 athletes",
            desires=["Style", "Performance"],
            objections=["Price"],
            competitive_landscape="Adidas and Puma lead.",
            creative_angles=[
                CreativeAngle(
                    name="The Everyday Athlete",
                    description="Real people. Real progress.",
                    rationale="Whitespace identified.",
                ),
            ],
            proven_hook_types=["Transformation stories"],
            sample_headlines=["What runners know"],
            creative_mandatories_explore=["Diversity"],
            creative_mandatories_avoid=["Elite-only"],
            category_trends=["Sustainability"],
        )
        md = BriefMarkdownRenderer().render(brief)

        # Check all section headers are present
        assert "## Brand Positioning" in md
        assert "## Primary Goal" in md
        assert "## Target Customer" in md
        assert "## Customer Desires" in md
        assert "## Objections to Address" in md
        assert "## Competitive Landscape" in md
        assert "## Recommended Creative Angles" in md
        assert "## Proven Hook Types" in md
        assert "## Sample Headlines" in md
        assert "## Creative Mandatories" in md
        assert "## Category Trends" in md

    def test_to_markdown_empty_brief(self) -> None:
        """Markdown for empty brief still renders with brand name."""
        brief = Brief(brand_name="")
        md = BriefMarkdownRenderer().render(brief)
        assert "Creative Brief:" in md
        assert "Brief Scout" in md

    def test_creative_angles_rendering(self) -> None:
        """Creative angles render with name, description, and rationale."""
        brief = Brief(
            brand_name="Nike",
            creative_angles=[
                CreativeAngle(
                    name="Angle A",
                    description="Description of angle A.",
                    rationale="Because research says so.",
                ),
            ],
        )
        md = BriefMarkdownRenderer().render(brief)
        assert "Angle A" in md
        assert "Description of angle A." in md
        assert "Because research says so." in md

    def test_default_construction(self) -> None:
        """Default Brief has empty fields."""
        brief = Brief()
        assert brief.brand_name == ""
        assert brief.creative_angles == []
        assert brief.desires == []
        assert brief.objections == []

    def test_sources_is_research_bundle(self) -> None:
        """Brief.sources is a ResearchBundle by default."""
        brief = Brief()
        assert isinstance(brief.sources, ResearchBundle)

    def test_to_dict(self) -> None:
        """to_dict returns a dictionary representation."""
        brief = Brief(brand_name="Nike", primary_goal="acquisition")
        d = brief.to_dict()
        assert isinstance(d, dict)
        assert d["brand_name"] == "Nike"
        assert d["primary_goal"] == "acquisition"


# ============================================================================
# TestResearchBundle
# ============================================================================


class TestResearchBundle:
    """Test the ResearchBundle model — construction and field access."""

    def test_default_construction(self) -> None:
        """Default ResearchBundle has all sub-models with defaults."""
        bundle = ResearchBundle()
        assert isinstance(bundle.brand_audit, BrandAuditResult)
        assert isinstance(bundle.competitor_scan, CompetitorScanResult)
        assert isinstance(bundle.trend_pulse, TrendPulseResult)
        assert isinstance(bundle.customer_voice, CustomerVoiceResult)
        assert isinstance(bundle.hook_mining, HookMiningResult)
        assert bundle.completed_at is not None

    def test_field_access(self) -> None:
        """All sub-result fields are accessible."""
        bundle = ResearchBundle()
        # Brand audit
        assert bundle.brand_audit.brand_positioning == ""
        assert bundle.brand_audit.key_messages == []

        # Competitor scan
        assert bundle.competitor_scan.competitors == []
        assert bundle.competitor_scan.whitespace_opportunities == []

        # Trend pulse
        assert bundle.trend_pulse.category_trends == []
        assert bundle.trend_pulse.timing_notes == ""

        # Customer voice
        assert bundle.customer_voice.customer_language == []
        assert bundle.customer_voice.top_desires == []

        # Hook mining
        assert bundle.hook_mining.proven_hook_types == []
        assert bundle.hook_mining.headline_starters == []

    def test_to_dict(self) -> None:
        """Sub-models can be serialized to dict."""
        bundle = ResearchBundle(
            brand_audit=BrandAuditResult(brand_positioning="Test"),
        )
        d = bundle.brand_audit.to_dict()
        assert d["brand_positioning"] == "Test"


# ============================================================================
# TestCreativeDirections
# ============================================================================


class TestCreativeDirections:
    """Test the CreativeDirections value object."""

    def test_defaults(self) -> None:
        """Default CreativeDirections has empty explore and avoid lists."""
        dirs = CreativeDirections()
        assert dirs.explore == []
        assert dirs.avoid == []

    def test_with_values(self) -> None:
        """CreativeDirections can be constructed with values."""
        dirs = CreativeDirections(
            explore=["athlete stories", "UGC content"],
            avoid=["studio shots", "over-polished"],
        )
        assert len(dirs.explore) == 2
        assert len(dirs.avoid) == 2
        assert "athlete stories" in dirs.explore
        assert "studio shots" in dirs.avoid

    def test_in_intake_data(self) -> None:
        """CreativeDirections works inside IntakeData."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas"],
            primary_goal="acquisition",
            target_customer="athletes",
            creative_directions=CreativeDirections(
                explore=["community stories"],
                avoid=["celebrity focus"],
            ),
        )
        assert data.creative_directions.explore == ["community stories"]


# ============================================================================
# TestCompetitorData
# ============================================================================


class TestCompetitorData:
    """Test the CompetitorData sub-model."""

    def test_defaults(self) -> None:
        """Default CompetitorData has empty fields."""
        cd = CompetitorData()
        assert cd.name == ""
        assert cd.primary_creative_angle == ""
        assert cd.key_messages == []
        assert cd.apparent_target_audience == ""
        assert cd.creative_gaps == ""

    def test_with_values(self) -> None:
        """CompetitorData can be constructed with values."""
        cd = CompetitorData(
            name="Adidas",
            primary_creative_angle="Heritage meets street culture.",
            key_messages=["Impossible Is Nothing"],
            apparent_target_audience="18-35 streetwear enthusiasts",
            creative_gaps="Less emotional storytelling.",
        )
        assert cd.name == "Adidas"
        assert len(cd.key_messages) == 1


# ============================================================================
# TestBriefSection
# ============================================================================


class TestBriefSection:
    """Test the BriefSection model."""

    def test_defaults(self) -> None:
        """Default BriefSection has empty fields."""
        section = BriefSection()
        assert section.title == ""
        assert section.content == ""
        assert section.bullets == []

    def test_with_values(self) -> None:
        """BriefSection can be constructed with values."""
        section = BriefSection(
            title="Overview",
            content="This is the overview.",
            bullets=["Point 1", "Point 2"],
        )
        assert section.title == "Overview"
        assert len(section.bullets) == 2


# ============================================================================
# TestChatMessage
# ============================================================================


class TestChatMessage:
    """Test the ChatMessage model."""

    def test_default_creation(self) -> None:
        """Default ChatMessage has user role, empty content, and a timestamp."""
        msg = ChatMessage()
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.timestamp is not None

    def test_explicit_creation(self) -> None:
        """ChatMessage can be created with all fields."""
        msg = ChatMessage(role="assistant", content="Hello there")
        assert msg.role == "assistant"
        assert msg.content == "Hello there"

    def test_valid_roles(self) -> None:
        """ChatMessage accepts valid roles."""
        for role in ("user", "assistant", "system"):
            msg = ChatMessage(role=role, content="test")
            assert msg.role == role
