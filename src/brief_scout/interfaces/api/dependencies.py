"""FastAPI dependency providers.

Provides typed ``Depends`` callables that read services from ``app.state``
instead of pulling them directly inside route handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import Request  # noqa: TC002

if TYPE_CHECKING:
    from brief_scout.application.services import BriefGenerationPipeline
    from brief_scout.application.use_cases import IntakeUseCase
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.config_port import ConfigurationPort
    from brief_scout.domain.ports.storage_port import BriefStoragePort
    from brief_scout.domain.ports.telemetry_port import TelemetryPort
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


def get_journey(request: Request) -> IntakeJourney:
    """Provide the intake journey from app.state."""
    return cast("IntakeJourney", request.app.state.journey)


def get_completeness_checker(request: Request) -> CompletenessChecker:
    """Provide the completeness checker from app.state."""
    return cast("CompletenessChecker", request.app.state.completeness_checker)


def get_intake_use_case(request: Request) -> IntakeUseCase:
    """Provide the intake use case from app.state."""
    return cast("IntakeUseCase", request.app.state.intake_use_case)


def get_pipeline(request: Request) -> BriefGenerationPipeline:
    """Provide the brief generation pipeline from app.state."""
    return cast("BriefGenerationPipeline", request.app.state.pipeline)
