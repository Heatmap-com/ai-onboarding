"""Open field-type handler registry for intake data merging.

New field types can be supported by registering a handler without modifying
``IntakeDataMerger``.
"""

from __future__ import annotations

from typing import Any, Protocol


class FieldTypeHandler(Protocol):
    """Protocol for a field-type merge handler."""

    def __call__(self, existing: Any, extracted: Any) -> Any:
        """Merge ``extracted`` into ``existing`` and return the result."""
        ...


class FieldTypeRegistry:
    """Registry mapping field type names to merge handlers.

    The registry is intentionally open: callers can register handlers for
    ``number``, ``boolean``, ``date``, or domain-specific types without
    changing ``IntakeDataMerger``.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._handlers: dict[str, FieldTypeHandler] = {}

    def register(self, field_type: str, handler: FieldTypeHandler) -> None:
        """Register a merge handler for ``field_type``."""
        self._handlers[field_type] = handler

    def get(self, field_type: str) -> FieldTypeHandler:
        """Return the handler for ``field_type``.

        Raises:
            ValueError: If no handler is registered for the type.
        """
        if field_type not in self._handlers:
            raise ValueError(f"No merge handler registered for field type: {field_type}")
        return self._handlers[field_type]

    def has(self, field_type: str) -> bool:
        """Return True if a handler is registered for ``field_type``."""
        return field_type in self._handlers

    def merge(self, field_type: str, existing: Any, extracted: Any) -> Any:
        """Merge ``extracted`` into ``existing`` using the registered handler."""
        return self.get(field_type)(existing, extracted)


# Built-in handlers


def _merge_string(existing: str, extracted: str) -> str:
    """Keep existing string if populated, otherwise use extracted."""
    if str(existing).strip():
        return existing
    if str(extracted).strip():
        return extracted
    return ""


def _merge_list(existing: list[Any], extracted: list[Any]) -> list[Any]:
    """Merge two lists, preserving order and uniqueness."""
    merged = list(existing)
    seen = set(merged)
    for item in extracted:
        if item and item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def create_default_registry() -> FieldTypeRegistry:
    """Return a registry with handlers for string, list, and object types."""
    registry = FieldTypeRegistry()
    registry.register("string", _merge_string)
    registry.register("list", _merge_list)
    # Object merging is recursive and needs the journey field metadata, so it
    # is handled specially by IntakeDataMerger; we register a placeholder that
    # simply returns the existing value.
    registry.register("object", lambda existing, _extracted: existing)
    return registry
