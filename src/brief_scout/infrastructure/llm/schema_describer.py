"""Schema describer — generates human-readable Pydantic schema summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


class SchemaDescriber:
    """Produces a concise, human-readable description of a Pydantic model."""

    def describe(self, schema: type[BaseModel]) -> str:
        """Return a comma-separated list of field names with their types."""
        fields: list[str] = []
        for name, info in schema.model_fields.items():
            annotation = info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append(f"{name} ({type_name})")
        return ", ".join(fields)
