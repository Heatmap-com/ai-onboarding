"""FastAPI routes with Server-Sent Events (SSE) streaming.

Per SPEC 8.1 — Provides REST endpoints for chat sessions, message
exchange, brief retrieval, and health checks. The SSE stream endpoint
is the primary delivery mechanism, streaming real-time progress events
as the pipeline executes.

Endpoints:
    POST /api/v1/chat/sessions        — Create a new chat session
    POST /api/v1/chat/{session_id}/message — Send message, get response
    GET  /api/v1/chat/{session_id}/stream  — SSE stream (primary)
    GET  /api/v1/briefs/{session_id}  — Retrieve a generated brief
    GET  /api/v1/health               — Health check
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from brief_scout.application.dto import (
    BriefResponse,
    ChatResponse,
    HealthResponse,
    MessageRequest,
    SessionResponse,
)
from brief_scout.domain.models import (
    BrandAuditResult,
    ChatSession,
    CompetitorScanResult,
    CreativeDirections,
    CustomerVoiceResult,
    HookMiningResult,
    IntakeData,
    ResearchBundle,
    TrendPulseResult,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from brief_scout.application.use_cases import (
        IntakeUseCase,
        ResearchUseCase,
        SynthesisUseCase,
    )

router = APIRouter(prefix="/api/v1")


@router.post("/chat/sessions", response_model=SessionResponse)
async def create_session(
    request: Request,
) -> SessionResponse:
    """Create a new chat session.

    Returns a fresh session with a generated UUID and ``intaking`` status.

    Args:
        request: FastAPI request object (for accessing app.state).

    Returns:
        SessionResponse with the new session ID and metadata.
    """
    session = ChatSession()
    storage = request.app.state.storage
    await storage.save_session(session)

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.post("/chat/{session_id}/message", response_model=ChatResponse)
async def send_message(
    session_id: str,
    request_body: MessageRequest,
    request: Request,
) -> ChatResponse:
    """Send a message and get the assistant response.

    Looks up the session, processes the message through the intake use
    case, and returns the assistant's reply.

    Args:
        session_id: The session identifier from the URL path.
        request_body: MessageRequest containing the user's message.
        request: FastAPI request object (for accessing app.state).

    Returns:
        ChatResponse with the assistant's message and session status.

    Raises:
        HTTPException: 404 if session not found.
    """
    storage = request.app.state.storage
    intake_use_case: IntakeUseCase = request.app.state.intake_use_case

    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await intake_use_case.process_message(
        session,
        request_body.message,
    )

    extracted_data: dict[str, Any] = result.extracted_data.model_dump()

    return ChatResponse(
        message=result.assistant_message,
        session_id=session_id,
        status=result.updated_session.status,
        extracted_data=extracted_data,
    )


@router.get("/chat/{session_id}/stream")
async def stream_message(
    session_id: str,
    message: str,
    request: Request,
) -> EventSourceResponse:
    """SSE endpoint for streaming the full pipeline.

    Streams events in real-time as the pipeline executes:
        1. ``intake``       — Intake processing result
        2. ``research``     — Research phase started
        3. ``research_step``— Individual research call completed (x5)
        4. ``synthesis``    — Synthesis started/completed
        5. ``brief``        — Final brief with markdown
        6. ``error``        — On any failure (recoverable)

    The research calls run sequentially within the generator so that
    each completion can be streamed to the client immediately. Each
    failed call yields a ``research_step`` with ``status: failed`` and
    the pipeline continues with default (empty) results.

    Args:
        session_id: The session identifier.
        message: The user's message text (query parameter).
        request: FastAPI request object (for accessing app.state).

    Returns:
        EventSourceResponse streaming SSE events.
    """
    storage = request.app.state.storage

    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def _wrapped_generator() -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding SSE events throughout the pipeline."""
        # Resolve dependencies fresh (avoid closure issues)
        storage_local = request.app.state.storage
        intake_uc: IntakeUseCase = request.app.state.intake_use_case
        research_uc: ResearchUseCase = request.app.state.research_use_case
        synthesis_uc: SynthesisUseCase = request.app.state.synthesis_use_case

        try:
            # ─── PHASE 1: INTAKE ───
            intake_result = await intake_uc.process_message(
                session,
                message,
            )

            yield _make_event(
                "intake",
                {
                    "message": intake_result.assistant_message,
                    "is_complete": intake_result.is_complete,
                    "session_id": session_id,
                    "status": intake_result.updated_session.status,
                },
            )

            # If intake not complete, stream ends after intake event
            if not intake_result.is_complete:
                return

            # ─── PHASE 2: RESEARCH ───
            yield _make_event(
                "research",
                {
                    "status": "started",
                    "steps": [
                        "Brand Audit",
                        "Competitor Scan",
                        "Trend Pulse",
                        "Customer Voice",
                        "Hook Mining",
                    ],
                },
            )

            # Use extracted intake data directly
            intake_data = intake_result.extracted_data

            # Execute 5 research calls with individual step events
            research_calls: list[tuple[str, Any]] = [
                ("Brand Audit", research_uc._call_brand_audit),
                ("Competitor Scan", research_uc._call_competitor_scan),
                ("Trend Pulse", research_uc._call_trend_pulse),
                ("Customer Voice", research_uc._call_customer_voice),
                ("Hook Mining", research_uc._call_hook_mining),
            ]

            default_map: dict[str, Any] = {
                "Brand Audit": BrandAuditResult(),
                "Competitor Scan": CompetitorScanResult(),
                "Trend Pulse": TrendPulseResult(),
                "Customer Voice": CustomerVoiceResult(),
                "Hook Mining": HookMiningResult(),
            }

            research_results: list[Any] = []
            for step_name, call_method in research_calls:
                try:
                    result = await call_method(intake_data)
                    research_results.append(result)
                    yield _make_event(
                        "research_step",
                        {"name": step_name, "status": "complete"},
                    )
                except Exception as step_exc:
                    research_results.append(default_map[step_name])
                    yield _make_event(
                        "research_step",
                        {
                            "name": step_name,
                            "status": "failed",
                            "error": str(step_exc),
                        },
                    )

            # Assemble ResearchBundle from results
            research_bundle = ResearchBundle(
                brand_audit=research_results[0]
                if isinstance(research_results[0], BrandAuditResult)
                else BrandAuditResult(),
                competitor_scan=research_results[1]
                if isinstance(research_results[1], CompetitorScanResult)
                else CompetitorScanResult(),
                trend_pulse=research_results[2]
                if isinstance(research_results[2], TrendPulseResult)
                else TrendPulseResult(),
                customer_voice=research_results[3]
                if isinstance(research_results[3], CustomerVoiceResult)
                else CustomerVoiceResult(),
                hook_mining=research_results[4]
                if isinstance(research_results[4], HookMiningResult)
                else HookMiningResult(),
            )

            # ─── PHASE 3: SYNTHESIS ───
            yield _make_event("synthesis", {"status": "started"})

            brief = await synthesis_uc.execute(intake_data, research_bundle)
            await storage_local.save_brief(session_id, brief)

            # Update session status to complete
            session.status = "complete"
            await storage_local.save_session(session)

            yield _make_event("synthesis", {"status": "complete"})

            # ─── PHASE 4: BRIEF ───
            markdown = brief.to_markdown()
            yield _make_event(
                "brief",
                {
                    "brief": brief.model_dump(),
                    "markdown": markdown,
                    "session_id": session_id,
                },
            )

        except Exception as exc:
            yield _make_event(
                "error",
                {
                    "message": str(exc),
                    "recoverable": True,
                    "session_id": session_id,
                },
            )

    return EventSourceResponse(_wrapped_generator())


def _dict_to_intake_data(data: dict[str, Any]) -> IntakeData:
    """Convert a plain dict to IntakeData, handling nested structures.

    Args:
        data: Dictionary (possibly from JSON or model_dump) with intake
            fields, including nested ``creative_directions``.

    Returns:
        Validated IntakeData instance.
    """
    if "creative_directions" in data and isinstance(data["creative_directions"], dict):
        cd = data["creative_directions"]
        data["creative_directions"] = CreativeDirections(
            explore=cd.get("explore", []),
            avoid=cd.get("avoid", []),
        )
    return IntakeData.model_validate(data)


def _make_event(
    event_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Build an SSE event dictionary.

    Args:
        event_type: The event type string (e.g., ``"intake"``, ``"brief"``).
        data: Event payload data.

    Returns:
        Dictionary with ``event`` key for the event type and ``data``
        key containing a JSON-serialized payload.
    """
    return {
        "event": event_type,
        "data": json.dumps(
            {
                "type": event_type,
                "timestamp": datetime.now(UTC).isoformat(),
                **data,
            },
            default=str,
        ),
    }


@router.get("/briefs/{session_id}", response_model=BriefResponse)
async def get_brief(
    session_id: str,
    request: Request,
) -> BriefResponse:
    """Retrieve a generated brief by session ID.

    Args:
        session_id: The session identifier.
        request: FastAPI request object (for accessing app.state).

    Returns:
        BriefResponse with the brief and markdown rendering.

    Raises:
        HTTPException: 404 if brief not found for the session.
    """
    storage = request.app.state.storage
    brief = await storage.get_brief(session_id)

    if brief is None:
        raise HTTPException(
            status_code=404,
            detail="Brief not found for this session",
        )

    return BriefResponse(
        session_id=session_id,
        brief=brief,
        markdown=brief.to_markdown(),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
) -> HealthResponse:
    """Health check endpoint.

    Returns service status, version, and available LLM providers.

    Args:
        request: FastAPI request object (for accessing app.state).

    Returns:
        HealthResponse with service metadata.
    """
    config = request.app.state.config

    providers = list(config.app_config.llm_providers.keys())

    return HealthResponse(
        status="ok",
        version=config.app_config.app_version,
        providers=providers,
    )
