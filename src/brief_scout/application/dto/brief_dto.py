"""Data Transfer Objects for brief output and health checks.

Per SPEC 10 — Defines response models for brief retrieval and
health check endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel

from brief_scout.domain.models import Brief


class BriefResponse(BaseModel):
    """Response for retrieving a generated brief.

    Attributes:
        session_id: The session this brief belongs to.
        brief: The complete Brief model.
        markdown: Rendered markdown representation for display.
    """

    session_id: str
    brief: Brief
    markdown: str


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Overall service status ("ok" or "degraded").
        version: Application version string.
        providers: List of available LLM provider names.
    """

    status: str
    version: str
    providers: list[str]
