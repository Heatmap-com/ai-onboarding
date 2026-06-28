"""Unit tests for prompt builders, template renderer, and markdown renderer."""

from __future__ import annotations

import pytest

from brief_scout.application.services.brief_markdown_renderer import BriefMarkdownRenderer
from brief_scout.application.services.intake_prompt_builder import IntakePromptBuilder
from brief_scout.application.services.journey_renderer import JourneyRenderer
from brief_scout.application.services.research_prompt_builder import ResearchPromptBuilder
from brief_scout.application.services.synthesis_prompt_builder import SynthesisPromptBuilder
from brief_scout.application.services.template_renderer import Jinja2TemplateRenderer
from brief_scout.domain.models import Brief, CreativeAngle
from brief_scout.domain.models.config import PromptTemplateConfig
from brief_scout.domain.models.intake import ChatMessage, IntakeData
from brief_scout.domain.models.journey import IntakeJourney, JourneyField, ObjectProperty


class TestJinja2TemplateRenderer:
    """Tests for the Jinja2 template renderer."""

    def test_renders_simple_template(self) -> None:
        """Variables should be substituted into the template."""
        renderer = Jinja2TemplateRenderer()
        result = renderer.render("Hello {{ name }}!", {"name": "Alex"})
        assert result == "Hello Alex!"

    def test_renders_default_return(self) -> None:
        """An empty template should render to an empty string."""
        renderer = Jinja2TemplateRenderer()
        assert renderer.render("", {}) == ""


class TestJourneyRenderer:
    """Tests for the journey template renderer."""

    @pytest.fixture
    def journey(self) -> IntakeJourney:
        """Return a journey with a few fields."""
        return IntakeJourney(
            fields=[
                JourneyField(
                    name="brand_name",
                    type="string",
                    required=True,
                    question_template="What brand?",
                    acknowledgement_template="Got it: {{ brand_name }}.",
                ),
                JourneyField(
                    name="competitors",
                    type="list",
                    required=True,
                    question_template="Who competes with {{ brand_name }}?",
                ),
                JourneyField(
                    name="creative_directions",
                    type="object",
                    required=False,
                    ask_when_missing=True,
                    question_template="Any creative directions?",
                    properties=[
                        ObjectProperty(name="explore", type="list"),
                        ObjectProperty(name="avoid", type="list"),
                    ],
                ),
            ],
        )

    def test_render_question(self, journey: IntakeJourney) -> None:
        """Questions should include context-aware acknowledgements."""
        renderer = JourneyRenderer()
        field = journey.get_field("competitors")
        assert field is not None
        intake = IntakeData(brand_name="Nike")
        question = renderer.render_question(journey, field, intake)
        assert "Got it: Nike." in question
        assert "Who competes with Nike?" in question

    def test_render_question_without_ack(self, journey: IntakeJourney) -> None:
        """When no prior fields are filled, acknowledgements are omitted."""
        renderer = JourneyRenderer()
        field = journey.get_field("brand_name")
        assert field is not None
        question = renderer.render_question(journey, field, IntakeData())
        assert question == "What brand?"

    def test_render_researching_message(self, journey: IntakeJourney) -> None:
        """The researching transition message should render."""
        renderer = JourneyRenderer()
        message = renderer.render_researching_message(journey, IntakeData(brand_name="Nike"))
        assert "running research" in message.lower()

    def test_render_extraction_schema(self, journey: IntakeJourney) -> None:
        """The extraction schema should list all fields."""
        renderer = JourneyRenderer()
        schema = renderer.render_extraction_schema(journey)
        assert '"brand_name": ""' in schema
        assert '"competitors": []' in schema
        assert '"creative_directions":' in schema


class TestIntakePromptBuilder:
    """Tests for the intake extraction prompt builder."""

    def test_build_extraction_prompt(self) -> None:
        """The prompt should include the rendered schema and transcript."""
        builder = IntakePromptBuilder()
        journey = IntakeJourney(
            fields=[
                JourneyField(name="brand_name", type="string", required=True),
            ],
        )
        messages = [
            ChatMessage(role="user", content="We're building creative for Nike"),
        ]
        prompt = builder.build_extraction_prompt("Schema:\n{{ schema }}", journey, messages)
        assert "brand_name" in prompt.system
        assert "User:" in prompt.user
        assert "Nike" in prompt.user


class TestResearchPromptBuilder:
    """Tests for the research prompt builder."""

    def test_substitutes_placeholders(self) -> None:
        """Placeholders wrapped in braces should be replaced."""
        template = PromptTemplateConfig(
            system="system",
            user="Brand {brand_name}, Category {category}",
        )
        prompt = ResearchPromptBuilder().build(
            template,
            {"brand_name": "Nike", "category": "apparel"},
        )
        assert prompt.user == "Brand Nike, Category apparel"
        assert prompt.system == "system"

    def test_leaves_unknown_placeholders(self) -> None:
        """Unknown placeholders should remain unchanged."""
        template = PromptTemplateConfig(user="Brand {brand_name}, {missing}")
        prompt = ResearchPromptBuilder().build(template, {"brand_name": "Nike"})
        assert "{missing}" in prompt.user


class TestSynthesisPromptBuilder:
    """Tests for the synthesis prompt builder."""

    def test_includes_intake_and_research_json(self) -> None:
        """The synthesis prompt should embed JSON payloads."""
        builder = SynthesisPromptBuilder()
        intake = IntakeData(brand_name="Nike")
        from brief_scout.domain.models.research import ResearchBundle

        research = ResearchBundle()
        template = PromptTemplateConfig(
            system="sys",
            user="Intake: {intake_json}\nResearch: {research_json}",
        )
        prompt = builder.build(template, intake, research)
        assert '"brand_name": "Nike"' in prompt.user
        assert '"completed_at"' in prompt.user


class TestBriefMarkdownRenderer:
    """Tests for the brief markdown renderer."""

    def test_renders_title_and_sections(self) -> None:
        """A populated brief should render markdown sections."""
        brief = Brief(
            brand_name="Nike",
            brand_positioning="Performance brand.",
            primary_goal="Acquisition",
            target_customer="Athletes",
            desires=["Style"],
            objections=["Price"],
            creative_angles=[
                CreativeAngle(name="Everyday Athlete", description="Real people."),
            ],
            sample_headlines=["Headline 1"],
            category_trends=["Sustainability"],
        )
        markdown = BriefMarkdownRenderer().render(brief)
        assert "# Creative Brief: Nike" in markdown
        assert "## Brand Positioning" in markdown
        assert "Performance brand." in markdown
        assert "## Customer Desires" in markdown
        assert "- Style" in markdown
        assert "### Angle 1: Everyday Athlete" in markdown

    def test_skips_empty_sections(self) -> None:
        """Empty sections should be omitted from the output."""
        brief = Brief(brand_name="X")
        markdown = BriefMarkdownRenderer().render(brief)
        assert "# Creative Brief: X" in markdown
        assert "## Brand Positioning" not in markdown
