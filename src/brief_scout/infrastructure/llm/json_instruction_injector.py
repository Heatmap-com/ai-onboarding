"""JSON instruction injector — appends schema constraints to a prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.ports.llm_port import Prompt
from brief_scout.infrastructure.llm.schema_describer import SchemaDescriber

if TYPE_CHECKING:
    from pydantic import BaseModel


class JsonInstructionInjector:
    """Appends JSON formatting instructions to a prompt's system message."""

    def __init__(self, describer: SchemaDescriber | None = None) -> None:
        """Initialize the injector with an optional schema describer."""
        self._describer = describer or SchemaDescriber()

    def inject(self, prompt: Prompt, schema: type[BaseModel]) -> Prompt:
        """Return a new prompt with JSON instructions appended to the system text."""
        schema_desc = self._describer.describe(schema)
        json_instruction = (
            "\n\nYou must respond with ONLY a valid JSON object matching "
            "this schema. No prose, no markdown, no code blocks. "
            f"The JSON fields are: {schema_desc}"
        )
        return Prompt(
            system=prompt.system + json_instruction,
            user=prompt.user,
            context=prompt.context,
        )
