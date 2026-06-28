"""Journey schema models for the declarative intake interview.

A Journey describes the fields to collect, their types, whether they are
required, the templates used to ask about them, and how they are merged.
The IntakeUseCase drives the conversation directly from this schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from jinja2 import Template
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import IntakeData


FieldType = Literal["string", "list", "object"]


class ObjectProperty(BaseModel):
    """A sub-field inside an object-typed JourneyField."""

    model_config = ConfigDict(frozen=False)

    name: str
    type: FieldType = "list"


class JourneyField(BaseModel):
    """A single field collected during the intake interview.

    Attributes:
        name: Attribute name on IntakeData.
        type: Field type — string, list, or object.
        required: Whether the field must be filled before research can start.
        ask_when_missing: Whether the assistant should explicitly ask for this
            field when it is empty. Some optional fields (e.g. brand_url) may be
            gathered opportunistically rather than asked about directly.
        question_template: Jinja2 template for the question asked when this field
            is missing. The IntakeData instance is available as the template context.
        acknowledgement_template: Jinja2 template rendered as part of the preamble
            once this field has been collected. Empty strings are skipped.
        properties: For object-typed fields, the sub-fields that can be merged.
    """

    model_config = ConfigDict(frozen=False)

    name: str
    type: FieldType = "string"
    required: bool = False
    ask_when_missing: bool = True
    question_template: str = ""
    acknowledgement_template: str = ""
    properties: list[ObjectProperty] = Field(default_factory=list)

    def is_empty(self, value: Any) -> bool:
        """Return True if ``value`` is considered empty for this field type."""
        if self.type == "list":
            return not value
        if self.type == "object":
            # An object is empty when all its declared properties are empty.
            if value is None:
                return True
            return all(not getattr(value, prop.name, None) for prop in self.properties)
        return not str(value).strip()

    def render_question(self, intake_data: IntakeData) -> str:
        """Render this field's question template against the intake data."""
        return Template(self.question_template).render(
            **intake_data.model_dump(),
        )

    def render_acknowledgement(self, intake_data: IntakeData) -> str:
        """Render this field's acknowledgement template against the intake data."""
        if not self.acknowledgement_template:
            return ""
        return Template(self.acknowledgement_template).render(
            **intake_data.model_dump(),
        )


class IntakeJourney(BaseModel):
    """Declarative schema for the entire conversational intake flow.

    Attributes:
        fields: Ordered list of fields to collect.
        researching_template: Jinja2 template rendered when intake is complete
            and the assistant is about to start research.
    """

    model_config = ConfigDict(frozen=False)

    fields: list[JourneyField] = Field(default_factory=list)
    researching_template: str = (
        "Perfect — I have everything I need. "
        "I'm now running research across 5 areas: brand audit, "
        "competitor scan, trend pulse, customer voice, and hook mining. "
        "This will take just a moment..."
    )

    def get_field(self, name: str) -> JourneyField | None:
        """Look up a field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    @property
    def required_fields(self) -> list[JourneyField]:
        """Return fields that must be filled before research can start."""
        return [f for f in self.fields if f.required]

    @property
    def optional_fields(self) -> list[JourneyField]:
        """Return non-required fields that may be asked explicitly."""
        return [f for f in self.fields if not f.required and f.ask_when_missing]

    def next_field(
        self,
        intake_data: IntakeData,
        asked_optional_questions: list[str],
    ) -> JourneyField | None:
        """Determine the next field to ask about, if any.

        Required fields take precedence. Once all required fields are filled,
        optional fields that have not yet been asked are offered one at a time.

        Args:
            intake_data: Current collected intake data.
            asked_optional_questions: Names of optional questions already asked.

        Returns:
            The next field to ask about, or None if the journey is complete.
        """
        for field in self.required_fields:
            if field.is_empty(getattr(intake_data, field.name)):
                return field

        for field in self.optional_fields:
            if field.name in asked_optional_questions:
                continue
            if field.is_empty(getattr(intake_data, field.name)):
                return field

        return None

    def is_complete(
        self,
        intake_data: IntakeData,
        asked_optional_questions: list[str] | None = None,
    ) -> bool:
        """Return True when there are no more fields to ask about."""
        return (
            self.next_field(
                intake_data,
                asked_optional_questions or [],
            )
            is None
        )

    def render_question(
        self,
        field: JourneyField,
        intake_data: IntakeData,
    ) -> str:
        """Render a question for ``field`` plus context-aware acknowledgements."""
        acknowledgements: list[str] = []
        for f in self.fields:
            if f.name == field.name:
                continue
            if f.is_empty(getattr(intake_data, f.name)):
                continue
            ack = f.render_acknowledgement(intake_data)
            if ack:
                acknowledgements.append(ack)

        question = field.render_question(intake_data)

        if acknowledgements:
            return f"{' '.join(acknowledgements)} {question}"
        return question

    def render_researching_message(self, intake_data: IntakeData) -> str:
        """Render the transition message when intake is complete."""
        return Template(self.researching_template).render(
            **intake_data.model_dump(),
        )

    def render_extraction_schema(self) -> str:
        """Render a JSON schema snippet describing all fields for LLM extraction."""
        lines: list[str] = ["{"]
        for field in self.fields:
            if field.type == "list":
                lines.append(f'  "{field.name}": [],')
            elif field.type == "object":
                props = ", ".join(f'"{p.name}": []' for p in field.properties)
                lines.append(f'  "{field.name}": {{{props}}},')
            else:
                lines.append(f'  "{field.name}": "",')
        lines.append("}")
        return "\n".join(lines)
