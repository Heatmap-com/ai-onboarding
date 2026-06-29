"""Research step port — contract for a single pluggable research step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

    from brief_scout.domain.models.intake import IntakeData


@runtime_checkable
class ResearchStep(Protocol):
    """A single pluggable research step.

    Implementations must declare a ``name`` class attribute and provide an
    ``execute`` coroutine that accepts intake data and returns a typed
    Pydantic result model.
    """

    name: str

    async def execute(self, intake_data: IntakeData) -> BaseModel:
        """Execute the step and return a typed result."""
        ...
