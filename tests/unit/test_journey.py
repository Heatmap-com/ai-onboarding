"""Unit tests for the declarative IntakeJourney schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from brief_scout.application.services.journey_renderer import JourneyRenderer
from brief_scout.domain.models.intake import IntakeData
from brief_scout.domain.models.journey import IntakeJourney, JourneyField
from brief_scout.infrastructure.config.journey_loader import JourneyLoader
from brief_scout.infrastructure.template import Jinja2TemplateRenderer


class TestJourneyField:
    """Tests for individual field behaviour."""

    def test_string_empty(self) -> None:
        """Empty string should be reported as empty."""
        field = JourneyField(name="x", type="string")
        assert field.is_empty("") is True
        assert field.is_empty("hello") is False

    def test_list_empty(self) -> None:
        """Empty list should be reported as empty."""
        field = JourneyField(name="x", type="list")
        assert field.is_empty([]) is True
        assert field.is_empty(["a"]) is False

    def test_object_empty(self) -> None:
        """Object is empty when all declared properties are empty."""
        from brief_scout.domain.models.intake import CreativeDirections

        field = JourneyField(
            name="dirs",
            type="object",
            properties=[
                {"name": "explore", "type": "list"},
                {"name": "avoid", "type": "list"},
            ],
        )
        assert field.is_empty(CreativeDirections()) is True
        assert field.is_empty(CreativeDirections(explore=["x"])) is False


class TestIntakeJourney:
    """Tests for the full journey schema."""

    @pytest.fixture
    def journey(self) -> IntakeJourney:
        """Provide a simple 3-field journey."""
        return IntakeJourney(
            fields=[
                JourneyField(
                    name="first_name",
                    type="string",
                    required=True,
                    question_template="Hi! What's your name?",
                ),
                JourneyField(
                    name="brand_name",
                    type="string",
                    required=True,
                    question_template="What brand, {{first_name}}?",
                    acknowledgement_template="Got it — {{brand_name}}.",
                ),
                JourneyField(
                    name="competitors",
                    type="list",
                    required=True,
                    question_template="Who are the competitors?",
                ),
            ],
        )

    @pytest.fixture
    def renderer(self) -> JourneyRenderer:
        """Provide a JourneyRenderer using the real Jinja2 adapter."""
        return JourneyRenderer(renderer=Jinja2TemplateRenderer())

    def test_next_field_returns_first_missing_required(self, journey: IntakeJourney) -> None:
        """Empty intake should ask for the first required field."""
        data = IntakeData()
        field = journey.next_field(data, [])
        assert field is not None
        assert field.name == "first_name"

    def test_next_field_moves_to_second_required(self, journey: IntakeJourney) -> None:
        """After first_name is collected, ask for brand_name."""
        data = IntakeData(first_name="Alex")
        field = journey.next_field(data, [])
        assert field is not None
        assert field.name == "brand_name"

    def test_is_complete_when_all_required_filled(self, journey: IntakeJourney) -> None:
        """All required fields filled means the journey is complete."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            competitors=["Adidas"],
        )
        assert journey.is_complete(data) is True

    def test_render_question_includes_acknowledgement(
        self, journey: IntakeJourney, renderer: JourneyRenderer
    ) -> None:
        """Question for competitors should acknowledge already-known brand."""
        data = IntakeData(
            first_name="Alex",
            brand_name="Nike",
        )
        competitors = journey.get_field("competitors")
        assert competitors is not None
        question = renderer.render_question(journey, competitors, data)
        assert "Got it — Nike." in question
        assert "Who are the competitors?" in question

    def test_render_question_uses_template_context(
        self, journey: IntakeJourney, renderer: JourneyRenderer
    ) -> None:
        """Question template should interpolate collected data."""
        data = IntakeData(first_name="Alex")
        brand_field = journey.get_field("brand_name")
        assert brand_field is not None
        question = renderer.render_question(journey, brand_field, data)
        assert "Alex" in question


class TestJourneyLoader:
    """Tests for loading the journey from YAML."""

    def test_loads_default_journey(self) -> None:
        """The default journey file should load and validate."""
        loader = JourneyLoader(config_dir="config")
        journey = loader.load()

        assert len(journey.fields) > 0
        first = journey.fields[0]
        assert first.name == "first_name"
        assert first.required is True

    def test_loads_demo_overlay(self, tmp_path: Path) -> None:
        """Environment-specific journey overlays should merge correctly."""
        base = tmp_path / "journey.yaml"
        base.write_text(
            "journey:\n  fields:\n    - name: first_name\n      type: string\n",
            encoding="utf-8",
        )
        overlay = tmp_path / "journey.demo.yaml"
        overlay.write_text(
            'journey:\n  researching_template: "Go, {{first_name}}!"\n',
            encoding="utf-8",
        )

        loader = JourneyLoader(config_dir=str(tmp_path), env="demo")
        journey = loader.load()

        assert journey.fields[0].name == "first_name"
        assert journey.researching_template == "Go, {{first_name}}!"


class TestLoadedJourney:
    """Contract tests for the real journey configuration."""

    @pytest.fixture
    def loaded_journey(self) -> IntakeJourney:
        """Load the default journey from config."""
        return JourneyLoader(config_dir="config").load()

    @pytest.fixture
    def renderer(self) -> JourneyRenderer:
        """Provide a JourneyRenderer using the real Jinja2 adapter."""
        return JourneyRenderer(renderer=Jinja2TemplateRenderer())

    def test_has_required_fields(self, loaded_journey: IntakeJourney) -> None:
        """The default journey should define the expected required fields."""
        required_names = {f.name for f in loaded_journey.required_fields}
        assert required_names == {
            "first_name",
            "brand_name",
            "competitors",
            "primary_goal",
            "target_customer",
        }

    def test_question_templates_render(
        self, loaded_journey: IntakeJourney, renderer: JourneyRenderer
    ) -> None:
        """Every question template should render without error for sample data."""
        sample = IntakeData(
            first_name="Alex",
            brand_name="Nike",
            brand_url="https://nike.com",
            competitors=["Adidas"],
            primary_goal="acquisition",
            target_customer="athletes",
            additional_context="Focus on sustainability",
        )
        for field in loaded_journey.fields:
            if field.ask_when_missing:
                rendered = renderer.render_question(loaded_journey, field, sample)
                assert isinstance(rendered, str)
                assert rendered.strip()

    def test_researching_template_renders(
        self, loaded_journey: IntakeJourney, renderer: JourneyRenderer
    ) -> None:
        """The researching transition template should render without error."""
        sample = IntakeData(first_name="Alex", brand_name="Nike")
        message = renderer.render_researching_message(loaded_journey, sample)
        assert "Alex" in message
        assert "research" in message.lower()
