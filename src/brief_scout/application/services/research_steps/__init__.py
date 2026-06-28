"""Research step implementations for the research pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

    from brief_scout.domain.models.intake import IntakeData


@runtime_checkable
class ResearchStep(Protocol):
    """A single pluggable research step."""

    name: str

    async def execute(self, intake_data: IntakeData) -> BaseModel:
        """Execute the step and return a typed result."""
        ...
