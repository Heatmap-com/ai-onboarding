"""Application factory — composition root for Brief Scout.

Per SPEC 8.2 — Wires all adapters, services, and use cases via
constructor injection. Creates and configures the FastAPI application
with routes and dependency state.

Usage:
    # Development
    uvicorn brief_scout.main:app --factory

    # Or directly
    python -m brief_scout.main
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from brief_scout.application.services import (
    BriefGenerationPipeline,
    DefaultResearchStepRegistry,
    IntakeDataDiffer,
    IntakeDataExtractor,
    JourneyAcknowledgementService,
)
from brief_scout.application.use_cases import (
    IntakeUseCase,
    ResearchUseCase,
    SynthesisUseCase,
)
from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger
from brief_scout.infrastructure.factories import (
    ConfigAdapterFactory,
    JourneySourceFactory,
    LLMAdapterFactory,
    StorageAdapterFactory,
    TelemetryAdapterFactory,
)
from brief_scout.infrastructure.llm.token_tracking_adapter import TokenTrackingLLM
from brief_scout.infrastructure.template import Jinja2TemplateRenderer
from brief_scout.interfaces.api import router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from brief_scout.domain.ports.journey_source_port import JourneySource
    from brief_scout.domain.ports.storage_port import BriefStoragePort


def create_app(
    config_dir: str | None = None,
    env: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    The composition root:
        1. Load configuration via ConfigAdapterFactory.
        2. Create telemetry adapter via TelemetryAdapterFactory.
        3. Create storage adapter via StorageAdapterFactory.
        4. Create LLM adapter via LLMAdapterFactory.
        5. Load journey via JourneySourceFactory.
        6. Wire use cases and the brief generation pipeline.
        7. Create FastAPI app, include router.
        8. Store dependencies on app.state.
    """
    # Resolve configuration
    if config_dir is None:
        config_dir = os.environ.get("BRIEF_SCOUT_CONFIG_DIR", "config")
    if env is None:
        env = os.environ.get("BRIEF_SCOUT_ENV", "development")

    # ─── 1. Configuration ───
    config = ConfigAdapterFactory().create(config_dir=config_dir, env=env)
    app_config = config.app_config

    # ─── 2. Telemetry ───
    telemetry = TelemetryAdapterFactory().create(
        adapter_id=app_config.telemetry.adapter,
        config=app_config.telemetry,
    )
    telemetry.log(
        "Application starting",
        level="INFO",
        app_name=app_config.app_name,
        version=app_config.app_version,
        env=env,
    )

    # ─── 3. Storage ───
    data_dir = os.environ.get("BRIEF_SCOUT_DATA_DIR", "./data")
    storage: BriefStoragePort = StorageAdapterFactory().create(
        adapter_id=app_config.storage_adapter,
        data_dir=data_dir,
        logger=telemetry,
    )
    telemetry.log(
        f"Storage adapter initialized: {app_config.storage_adapter}",
        level="DEBUG",
    )

    # ─── 4. LLM Adapter ───
    provider_name = app_config.default_llm_provider
    provider_config = config.get_provider_config(provider_name)
    llm = LLMAdapterFactory().create(provider_config, telemetry=telemetry)

    # Optionally wrap the LLM with token/cost tracking.
    track_tokens = os.environ.get("BRIEF_SCOUT_TRACK_TOKENS", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if track_tokens:
        llm = TokenTrackingLLM(llm, model=provider_config.model or "gpt-4o-mini")
        telemetry.log(
            f"Token tracking enabled for {llm.provider_name} ({llm._model})",
            level="INFO",
        )

    telemetry.log(
        f"LLM adapter initialized: {llm.provider_name}",
        level="DEBUG",
    )

    # ─── 5. Journey + Domain Services ───
    journey_source: JourneySource = JourneySourceFactory().create(
        config_dir=config_dir,
        env=env,
    )
    journey = journey_source.load()
    template_renderer = Jinja2TemplateRenderer()
    completeness_checker = CompletenessChecker(
        journey=journey,
        telemetry=telemetry,
    )
    merger = IntakeDataMerger(journey=journey)

    # ─── 6. Use Cases + Pipeline ───
    intake_extractor = IntakeDataExtractor(
        llm=llm,
        journey=journey,
        renderer=template_renderer,
        provider_config_source=config,
        logger=telemetry,
    )
    intake_acknowledgement_service = JourneyAcknowledgementService(
        renderer=template_renderer,
    )
    intake_differ = IntakeDataDiffer(journey=journey)

    intake_use_case = IntakeUseCase(
        extractor=intake_extractor,
        acknowledgement_service=intake_acknowledgement_service,
        differ=intake_differ,
        storage=storage,
        completeness_checker=completeness_checker,
        merger=merger,
        logger=telemetry,
        journey=journey,
        extraction_system=config.app_config.prompts.extraction_system,
    )
    research_step_registry = DefaultResearchStepRegistry(
        prompts=config.app_config.prompts.research_steps,
        llm=llm,
    )
    research_use_case = ResearchUseCase(
        registry=research_step_registry,
        telemetry=telemetry,
    )
    synthesis_use_case = SynthesisUseCase(
        llm=llm,
        config=config,
        telemetry=telemetry,
    )

    # Build the research pipeline from the configured research steps.
    # ResearchUseCase is the composition helper that knows how to map prompts
    # and LLM adapters onto the pluggable ResearchPipeline.
    research_pipeline = research_use_case.build_pipeline()
    pipeline = BriefGenerationPipeline(
        intake_use_case=intake_use_case,
        research_pipeline=research_pipeline,
        synthesis_use_case=synthesis_use_case,
        storage=storage,
    )

    # ─── 7. FastAPI Application ───
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan — startup and shutdown hooks."""
        telemetry.log("Application startup complete", level="INFO")
        yield
        telemetry.log("Application shutting down", level="INFO")

    app = FastAPI(
        title=app_config.app_name,
        version=app_config.app_version,
        description=(
            "Conversational brief intake + research agent. "
            "Chat through natural questions, then the system "
            "extracts structured data, runs research, "
            "and synthesizes a fully populated creative brief."
        ),
        lifespan=lifespan,
    )

    # Include API routes
    app.include_router(router)

    # Store all dependencies on app.state for route access
    app.state.config = config
    app.state.telemetry = telemetry
    app.state.storage = storage
    app.state.llm = llm
    app.state.token_usage = llm.token_usage if isinstance(llm, TokenTrackingLLM) else None
    app.state.completeness_checker = completeness_checker
    app.state.completeness_check_port = completeness_checker
    app.state.journey = journey
    app.state.template_renderer = template_renderer
    app.state.intake_use_case = intake_use_case
    app.state.intake_port = intake_use_case
    app.state.research_use_case = research_use_case
    app.state.synthesis_use_case = synthesis_use_case
    app.state.synthesis_port = synthesis_use_case
    app.state.research_pipeline = research_pipeline
    app.state.research_pipeline_port = research_pipeline
    app.state.pipeline = pipeline

    telemetry.log(
        "Application factory complete — all dependencies wired",
        level="INFO",
    )

    return app


def main() -> None:
    """Entry point for running the application with uvicorn."""
    import uvicorn

    host = os.environ.get("BRIEF_SCOUT_HOST", "0.0.0.0")
    port = int(os.environ.get("BRIEF_SCOUT_PORT", "8000"))
    reload = os.environ.get("BRIEF_SCOUT_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "brief_scout.main:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


# Application instance for ASGI servers (gunicorn, etc.)
# Usage: uvicorn brief_scout.main:app --factory
app = create_app

if __name__ == "__main__":
    main()
