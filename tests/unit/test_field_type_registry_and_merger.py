"""Unit tests for FieldTypeRegistry and IntakeDataMerger."""

from __future__ import annotations

import pytest

from brief_scout.domain.models.intake import CreativeDirections, IntakeData
from brief_scout.domain.models.journey import IntakeJourney, JourneyField, ObjectProperty
from brief_scout.domain.services.field_type_registry import (
    FieldTypeRegistry,
    create_default_registry,
)
from brief_scout.domain.services.intake_data_merger import IntakeDataMerger


class TestFieldTypeRegistry:
    """Tests for the open field-type registry."""

    def test_register_and_get(self) -> None:
        """Handlers can be registered and retrieved."""
        registry = FieldTypeRegistry()
        registry.register("custom", lambda existing, extracted: f"{existing}:{extracted}")

        handler = registry.get("custom")
        assert handler("a", "b") == "a:b"

    def test_has_returns_false_for_unregistered(self) -> None:
        """``has`` should return False when no handler is registered."""
        registry = FieldTypeRegistry()
        assert registry.has("missing") is False

    def test_has_returns_true_for_registered(self) -> None:
        """``has`` should return True for a registered handler."""
        registry = create_default_registry()
        assert registry.has("string") is True
        assert registry.has("list") is True
        assert registry.has("object") is True

    def test_get_missing_raises(self) -> None:
        """Retrieving an unregistered handler should raise ValueError."""
        registry = FieldTypeRegistry()
        with pytest.raises(ValueError, match="No merge handler registered"):
            registry.get("missing")

    def test_default_registry_string_handler(self) -> None:
        """The default string handler keeps existing when present."""
        registry = create_default_registry()
        handler = registry.get("string")
        assert handler("existing", "extracted") == "existing"
        assert handler("", "extracted") == "extracted"
        assert handler("  ", "") == ""

    def test_default_registry_list_handler(self) -> None:
        """The default list handler appends unique extracted items."""
        registry = create_default_registry()
        handler = registry.get("list")
        assert handler(["a"], ["b", "a"]) == ["a", "b"]
        assert handler([], ["", "c"]) == ["c"]


class TestIntakeDataMerger:
    """Tests for type-aware intake data merging."""

    @pytest.fixture
    def journey(self) -> IntakeJourney:
        """Return a journey covering string, list, and object fields."""
        return IntakeJourney(
            fields=[
                JourneyField(name="first_name", type="string", required=True),
                JourneyField(name="brand_name", type="string", required=True),
                JourneyField(name="competitors", type="list", required=True),
                JourneyField(
                    name="creative_directions",
                    type="object",
                    required=False,
                    properties=[
                        ObjectProperty(name="explore", type="list"),
                        ObjectProperty(name="avoid", type="list"),
                    ],
                ),
            ],
        )

    def test_merge_preserves_existing_string(self, journey: IntakeJourney) -> None:
        """String fields keep existing value when already populated."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData(first_name="Alex")
        extracted = IntakeData(first_name="Jordan")
        merged = merger.merge(existing, extracted)
        assert merged.first_name == "Alex"

    def test_merge_uses_extracted_string_when_existing_empty(self, journey: IntakeJourney) -> None:
        """String fields fall back to extracted value when existing is empty."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData()
        extracted = IntakeData(brand_name="Nike")
        merged = merger.merge(existing, extracted)
        assert merged.brand_name == "Nike"

    def test_merge_appends_unique_list_items(self, journey: IntakeJourney) -> None:
        """List fields merge without duplicates."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData(competitors=["Adidas"])
        extracted = IntakeData(competitors=["Puma", "Adidas"])
        merged = merger.merge(existing, extracted)
        assert merged.competitors == ["Adidas", "Puma"]

    def test_merge_object_when_existing_none(self, journey: IntakeJourney) -> None:
        """Object fields use extracted value when existing is None."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData()
        extracted = IntakeData(creative_directions=CreativeDirections(explore=["a"]))
        merged = merger.merge(existing, extracted)
        assert merged.creative_directions.explore == ["a"]

    def test_merge_object_when_extracted_none(self, journey: IntakeJourney) -> None:
        """Object fields keep existing value when extracted is None."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData(creative_directions=CreativeDirections(explore=["a"]))
        extracted = IntakeData()
        merged = merger.merge(existing, extracted)
        assert merged.creative_directions.explore == ["a"]

    def test_merge_object_properties(self, journey: IntakeJourney) -> None:
        """Object properties are merged recursively."""
        merger = IntakeDataMerger(journey)
        existing = IntakeData(
            creative_directions=CreativeDirections(
                explore=["authenticity"],
                avoid=["polished"],
            ),
        )
        extracted = IntakeData(
            creative_directions=CreativeDirections(
                explore=["community"],
                avoid=["generic"],
            ),
        )
        merged = merger.merge(existing, extracted)
        assert set(merged.creative_directions.explore) == {"authenticity", "community"}
        assert set(merged.creative_directions.avoid) == {"polished", "generic"}

    def test_custom_registry_handler(self, journey: IntakeJourney) -> None:
        """A custom handler can extend merging behavior."""
        registry = create_default_registry()
        registry.register("string", lambda existing, extracted: f"{existing}|{extracted}")
        merger = IntakeDataMerger(journey, registry=registry)
        existing = IntakeData(first_name="Alex")
        extracted = IntakeData(first_name="Jordan")
        merged = merger.merge(existing, extracted)
        assert merged.first_name == "Alex|Jordan"
