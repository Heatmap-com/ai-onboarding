"""Pipeline event — domain event emitted by pipeline stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineEvent(BaseModel):
    """Domain event emitted by pipeline stages.

    Attributes:
        stage: The pipeline stage that emitted the event (e.g., ``intake``,
            ``research``, ``synthesis``, ``brief``).
        status: The status of the stage (e.g., ``started``, ``progress``,
            ``complete``, ``failed``).
        payload: Arbitrary event-specific data.
    """

    stage: str = ""
    status: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
