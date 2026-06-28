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

from brief_scout.application.use_cases import (
    IntakeUseCase,
    ResearchUseCase,
    SynthesisUseCase,
)
from brief_scout.domain.services import CompletenessChecker, IntakeDataMerger
from brief_scout.interfaces.api import router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from brief_scout.domain.models.config import LLMProviderConfig
    from brief_scout.domain.ports import LLMPort, TelemetryPort
    from brief_scout.domain.ports.storage_port import BriefStoragePort


def create_app(
    config_dir: str | None = None,
    env: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    The composition root:
        1. Load configuration via YAMLConfigAdapter.
        2. Create telemetry adapter (local file).
        3. Create storage adapter (in-memory or file system).
        4. Create LLM adapter (FakeLLMAdapter from config).
        5. Wire use cases with injected dependencies.
        6. Create FastAPI app, include router.
        7. Store all dependencies on app.state.

    Args:
        config_dir: Path to configuration directory. Defaults to
            ``./config`` relative to the project root.
        env: Environment name (e.g., ``development``, ``production``).
            Defaults to the ``BRIEF_SCOUT_ENV`` environment variable
            or ``development``.

    Returns:
        Configured FastAPI application with all routes and dependencies.
    """
    # Resolve configuration
    if config_dir is None:
        config_dir = os.environ.get("BRIEF_SCOUT_CONFIG_DIR", "config")
    if env is None:
        env = os.environ.get("BRIEF_SCOUT_ENV", "development")

    # ─── 1. Configuration ───
    from brief_scout.infrastructure.config.yaml_config_adapter import (
        YAMLConfigAdapter,
    )

    config = YAMLConfigAdapter(config_dir=config_dir, env=env)
    app_config = config.app_config

    # ─── 2. Telemetry ───
    from brief_scout.infrastructure.telemetry.local_file_adapter import (
        LocalFileTelemetryAdapter,
    )

    telemetry = LocalFileTelemetryAdapter(
        log_dir=app_config.telemetry.log_dir,
        log_level=app_config.telemetry.log_level,
    )
    telemetry.log(
        "Application starting",
        level="INFO",
        app_name=app_config.app_name,
        version=app_config.app_version,
        env=env,
    )

    # ─── 3. Storage ───
    storage_adapter_name = app_config.storage_adapter
    storage: BriefStoragePort
    if storage_adapter_name == "file_system":
        from brief_scout.infrastructure.storage.file_system_adapter import (
            FileSystemStorageAdapter,
        )

        storage = FileSystemStorageAdapter(data_dir="./data")
    else:
        from brief_scout.infrastructure.storage.in_memory_adapter import (
            InMemoryStorageAdapter,
        )

        storage = InMemoryStorageAdapter()

    telemetry.log(
        f"Storage adapter initialized: {storage_adapter_name}",
        level="DEBUG",
    )

    # ─── 4. LLM Adapter ───
    provider_name = app_config.default_llm_provider
    provider_config = config.get_provider_config(provider_name)

    # Import and instantiate the adapter class from config
    llm = _create_llm_adapter(provider_config, telemetry)
    telemetry.log(
        f"LLM adapter initialized: {llm.provider_name}",
        level="DEBUG",
    )

    # ─── 5. Journey + Domain Services ───
    from brief_scout.infrastructure.config.journey_loader import JourneyLoader

    journey = JourneyLoader(config_dir=config_dir, env=env).load()
    completeness_checker = CompletenessChecker(
        journey=journey,
        telemetry=telemetry,
    )
    merger = IntakeDataMerger(journey=journey)

    # ─── 6. Use Cases (with dependency injection) ───
    intake_use_case = IntakeUseCase(
        llm=llm,
        config=config,
        telemetry=telemetry,
        storage=storage,
        journey=journey,
        completeness_checker=completeness_checker,
        merger=merger,
    )
    research_use_case = ResearchUseCase(
        llm=llm,
        config=config,
        telemetry=telemetry,
    )
    synthesis_use_case = SynthesisUseCase(
        llm=llm,
        config=config,
        telemetry=telemetry,
    )

    # ─── 7. FastAPI Application ───
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan — startup and shutdown hooks."""
        telemetry.log(
            "Application startup complete",
            level="INFO",
        )
        yield
        telemetry.log(
            "Application shutting down",
            level="INFO",
        )

    app = FastAPI(
        title=app_config.app_name,
        version=app_config.app_version,
        description=(
            "Conversational brief intake + research agent. "
            "Chat through 5-7 natural questions, then the system "
            "extracts structured data, fires 5 parallel research calls, "
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
    app.state.completeness_checker = completeness_checker
    app.state.journey = journey
    app.state.intake_use_case = intake_use_case
    app.state.research_use_case = research_use_case
    app.state.synthesis_use_case = synthesis_use_case

    telemetry.log(
        "Application factory complete — all dependencies wired",
        level="INFO",
    )

    return app


def _create_llm_adapter(
    provider_config: LLMProviderConfig,
    telemetry: TelemetryPort,
) -> LLMPort:
    """Dynamically instantiate the configured LLM adapter.

    Supports:
        - ``brief_scout.infrastructure.llm.fake_llm_adapter.FakeLLMAdapter``
        - Future real adapters via adapter_class config.

    Args:
        provider_config: Configuration for the LLM provider.
        telemetry: Telemetry adapter for the LLM to use.

    Returns:
        Instantiated LLMPort implementation.
    """
    adapter_class_path = provider_config.adapter_class

    # Default to FakeLLMAdapter if not specified
    if not adapter_class_path or adapter_class_path.endswith("FakeLLMAdapter"):
        from brief_scout.infrastructure.llm.fake_llm_adapter import (
            FakeLLMAdapter,
        )

        extras = provider_config.model_extra or {}
        return FakeLLMAdapter(
            fixture_dir=extras.get("fixture_dir", "tests/fixtures/llm_responses"),
            default_fixture=extras.get("default_fixture", "default"),
            latency_ms=extras.get("latency_ms", 50.0),
            telemetry=telemetry,
            demo_journey_path=extras.get("demo_journey_path"),
        )

    # Dynamic import for other adapter classes
    module_path, class_name = adapter_class_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    adapter = adapter_cls(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url,
        model=provider_config.model,
        temperature=provider_config.temperature,
        max_tokens=provider_config.max_tokens,
        timeout_seconds=provider_config.timeout_seconds,
        telemetry=telemetry,
    )
    return adapter  # type: ignore[no-any-return]


def main() -> None:
    """Entry point for running the application with uvicorn."""
    import uvicorn

    host = os.environ.get("BRIEF_SCOUT_HOST", "0.0.0.0")
    port = int(os.environ.get("BRIEF_SCOUT_PORT", "8000"))
    reload = os.environ.get("BRIEF_SCOUT_RELOAD", "false").lower() == "true"

    # Use the factory pattern — uvicorn calls create_app()
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
