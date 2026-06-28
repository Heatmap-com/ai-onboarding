"""Generic intake data merger.

Merges newly extracted IntakeData into existing data using the declarative
journey schema. This replaces hand-written per-field merge logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import FieldType, IntakeJourney, JourneyField


class IntakeDataMerger:
    """Merge extracted intake data into existing data using a journey schema.

    Attributes:
        journey: The intake journey describing field types and rules.
    """

    def __init__(self, journey: IntakeJourney) -> None:
        """Initialize the merger with a journey schema.

        Args:
            journey: The intake journey to use for type-aware merging.
        """
        self._journey = journey

    def merge(self, existing: IntakeData, extracted: IntakeData) -> IntakeData:
        """Return a new IntakeData with extracted values merged into existing.

        Rules:
        - String fields: keep existing value if present, otherwise use extracted.
        - List fields: append unique extracted items to existing items.
        - Object fields: recursively merge declared list/string properties.

        Args:
            existing: Previously stored intake data.
            extracted: Newly extracted intake data.

        Returns:
            A merged IntakeData instance.
        """
        merged = existing.model_copy(deep=True)

        for field in self._journey.fields:
            existing_value = getattr(merged, field.name)
            extracted_value = getattr(extracted, field.name)
            merged_value = self._merge_field(field, existing_value, extracted_value)
            setattr(merged, field.name, merged_value)

        return merged

    def _merge_field(
        self,
        field: JourneyField,
        existing_value: Any,
        extracted_value: Any,
    ) -> Any:
        """Merge a single field based on its type."""
        if field.type == "string":
            return self._merge_string(existing_value, extracted_value)

        if field.type == "list":
            return self._merge_list(existing_value, extracted_value)

        if field.type == "object":
            return self._merge_object(field, existing_value, extracted_value)

        # FieldType is an exhaustive literal, but keep a defensive fallback.
        raise ValueError(f"Unknown field type: {field.type}")

    @staticmethod
    def _merge_string(existing: str, extracted: str) -> str:
        """Keep existing string if populated, otherwise use extracted."""
        if str(existing).strip():
            return existing
        if str(extracted).strip():
            return extracted
        return ""

    @staticmethod
    def _merge_list(existing: list[str], extracted: list[str]) -> list[str]:
        """Merge two lists, preserving order and uniqueness."""
        merged = list(existing)
        seen = set(merged)
        for item in extracted:
            if item and item not in seen:
                merged.append(item)
                seen.add(item)
        return merged

    def _merge_object(
        self,
        field: JourneyField,
        existing: Any,
        extracted: Any,
    ) -> Any:
        """Recursively merge declared properties of an object field."""
        if existing is None:
            return extracted
        if extracted is None:
            return existing

        result = existing.model_copy(deep=True)
        for prop in field.properties:
            existing_prop = getattr(result, prop.name)
            extracted_prop = getattr(extracted, prop.name)
            merged_prop = self._merge_property(prop.type, existing_prop, extracted_prop)
            setattr(result, prop.name, merged_prop)
        return result

    @staticmethod
    def _merge_property(prop_type: FieldType, existing: Any, extracted: Any) -> Any:
        """Merge a single object property."""
        if prop_type == "list":
            return IntakeDataMerger._merge_list(existing or [], extracted or [])
        return IntakeDataMerger._merge_string(existing or "", extracted or "")
