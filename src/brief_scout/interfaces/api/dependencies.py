"""FastAPI dependency providers.

Provides typed ``Depends`` callables that read services from ``app.state``
instead of pulling them directly inside route handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import Request  # noqa: TC002

from brief_scout.application.services.brief_markdown_renderer import (  # noqa: TC001
    BriefMarkdownRenderer,
)

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports import (
        BriefReader,
        BriefStoragePort,
        BriefWriter,
        CompletenessCheckPort,
        ConfigurationPort,
        IntakePort,
        PipelinePort,
        ResearchPipelinePort,
        SessionReader,
        SessionStoragePort,
        SessionWriter,
        SynthesisPort,
        TelemetryPort,
    )
    from brief_scout.domain.services import CompletenessChecker


def get_config(request: Request) -> ConfigurationPort:
    """Provide the configuration port from app.state."""
    return cast("ConfigurationPort", request.app.state.config)


def get_telemetry(request: Request) -> TelemetryPort:
    """Provide the telemetry port from app.state."""
    return cast("TelemetryPort", request.app.state.telemetry)


def get_storage(request: Request) -> BriefStoragePort:
    """Provide the storage port from app.state."""
    return cast("BriefStoragePort", request.app.state.storage)


def get_session_reader(request: Request) -> SessionReader:
    """Provide the session reader port from app.state."""
    return cast("SessionReader", request.app.state.storage)


def get_session_writer(request: Request) -> SessionWriter:
    """Provide the session writer port from app.state."""
    return cast("SessionWriter", request.app.state.storage)


def get_session_storage(request: Request) -> SessionStoragePort:
    """Provide the combined session storage port from app.state."""
    return cast("SessionStoragePort", request.app.state.storage)


def get_brief_reader(request: Request) -> BriefReader:
    """Provide the brief reader port from app.state."""
    return cast("BriefReader", request.app.state.storage)


def get_brief_writer(request: Request) -> BriefWriter:
    """Provide the brief writer port from app.state."""
    return cast("BriefWriter", request.app.state.storage)


def get_journey(request: Request) -> IntakeJourney:
    """Provide the intake journey from app.state."""
    return cast("IntakeJourney", request.app.state.journey)


def get_completeness_checker(request: Request) -> CompletenessChecker:
    """Provide the completeness checker from app.state."""
    return cast("CompletenessChecker", request.app.state.completeness_checker)


def get_completeness_check_port(request: Request) -> CompletenessCheckPort:
    """Provide the completeness checker port from app.state."""
    return cast("CompletenessCheckPort", request.app.state.completeness_checker)


def get_intake_port(request: Request) -> IntakePort:
    """Provide the intake port from app.state."""
    return cast("IntakePort", request.app.state.intake_use_case)


def get_research_pipeline_port(request: Request) -> ResearchPipelinePort:
    """Provide the research pipeline port from app.state."""
    return cast("ResearchPipelinePort", request.app.state.research_pipeline)


def get_synthesis_port(request: Request) -> SynthesisPort:
    """Provide the synthesis port from app.state."""
    return cast("SynthesisPort", request.app.state.synthesis_use_case)


def get_pipeline(request: Request) -> PipelinePort:
    """Provide the brief generation pipeline from app.state."""
    return cast("PipelinePort", request.app.state.pipeline)


def get_brief_markdown_renderer(request: Request) -> BriefMarkdownRenderer:
    """Provide the brief markdown renderer from app.state."""
    return cast("BriefMarkdownRenderer", request.app.state.brief_markdown_renderer)
