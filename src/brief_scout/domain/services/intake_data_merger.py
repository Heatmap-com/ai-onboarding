"""Generic intake data merger.

Merges newly extracted IntakeData into existing data using the declarative
journey schema. Field-type behavior is extensible through a
``FieldTypeRegistry``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brief_scout.domain.services.field_type_registry import (
    FieldTypeRegistry,
    create_default_registry,
)

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.models.journey import IntakeJourney, JourneyField


class IntakeDataMerger:
    """Merge extracted intake data into existing data using a journey schema.

    Attributes:
        journey: The intake journey describing field types and rules.
        registry: Optional custom field-type registry. When omitted, the
            default registry (string, list, object) is used.
    """

    def __init__(
        self,
        journey: IntakeJourney,
        registry: FieldTypeRegistry | None = None,
    ) -> None:
        """Initialize the merger with a journey schema and optional registry.

        Args:
            journey: The intake journey to use for type-aware merging.
            registry: Optional custom field-type registry.
        """
        self._journey = journey
        self._registry = registry or create_default_registry()

    def merge(self, existing: IntakeData, extracted: IntakeData) -> IntakeData:
        """Return a new IntakeData with extracted values merged into existing.

        Rules:
        - String fields: keep existing value if present, otherwise use extracted.
        - List fields: append unique extracted items to existing items.
        - Object fields: recursively merge declared list/string properties.

        New rules can be added by registering handlers on the registry.

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
        """Merge a single field based on its registered type handler."""
        if field.type == "object":
            return self._merge_object(field, existing_value, extracted_value)

        handler = self._registry.get(field.type)
        return handler(existing_value, extracted_value)

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

    def _merge_property(self, prop_type: str, existing: Any, extracted: Any) -> Any:
        """Merge a single object property."""
        if prop_type == "list":
            return self._registry.merge("list", existing or [], extracted or [])
        return self._registry.merge("string", existing or "", extracted or "")
