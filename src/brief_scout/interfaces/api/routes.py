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
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from brief_scout.application.dto import (
    BriefResponse,
    ChatResponse,
    HealthResponse,
    MessageRequest,
    SessionResponse,
)
from brief_scout.application.services import PipelineEvent
from brief_scout.domain.models import ChatSession
from brief_scout.domain.ports.config_port import ConfigurationPort  # noqa: TC001
from brief_scout.domain.ports.pipeline_port import PipelinePort  # noqa: TC001
from brief_scout.domain.ports.storage_port import BriefStoragePort  # noqa: TC001
from brief_scout.interfaces.api.dependencies import (
    get_config,
    get_pipeline,
    get_storage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

router = APIRouter(prefix="/api/v1")


@router.post("/chat/sessions", response_model=SessionResponse)
async def create_session(
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
) -> SessionResponse:
    """Create a new chat session.

    Returns a fresh session with a generated UUID and ``intaking`` status.
    """
    session = ChatSession()
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
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
    pipeline: Annotated[PipelinePort, Depends(get_pipeline)],
) -> ChatResponse:
    """Send a message and get the assistant response.

    Uses the brief generation pipeline's intake stage. If intake completes,
    research and synthesis are also executed and the final assistant message
    is returned.
    """
    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    assistant_message = ""
    extracted_data: dict[str, Any] = {}
    async for event in pipeline.run(session, request_body.message):
        if event.stage == "intake":
            assistant_message = event.payload.get("message", "")
            extracted_data = event.payload.get("extracted_data", {})
            # The non-streaming message endpoint stops once intake is complete.
            # Research and synthesis run through the SSE /stream endpoint so
            # clients get real-time progress and we don't execute the pipeline
            # twice when both endpoints are used.
            if event.payload.get("is_complete"):
                break

    return ChatResponse(
        message=assistant_message,
        session_id=session_id,
        status=session.status,
        extracted_data=extracted_data,
    )


@router.get("/chat/{session_id}/stream")
async def stream_message(
    session_id: str,
    message: str,
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
    pipeline: Annotated[PipelinePort, Depends(get_pipeline)],
) -> EventSourceResponse:
    """SSE endpoint for streaming the full pipeline.

    Streams events in real-time as the brief generation pipeline executes:
        1. ``intake``       — Intake processing result
        2. ``research``     — Research phase started
        3. ``research_step``— Individual research call completed
        4. ``synthesis``    — Synthesis started/completed
        5. ``brief``        — Final brief with markdown
        6. ``error``        — On any failure (recoverable)
    """
    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def _wrapped_generator() -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding SSE events throughout the pipeline."""
        try:
            async for event in pipeline.run(session, message):
                yield _make_event(event)
        except Exception as exc:
            yield _make_event(
                PipelineEvent(
                    stage="error",
                    status="failed",
                    payload={
                        "message": str(exc),
                        "recoverable": True,
                        "session_id": session_id,
                    },
                )
            )

    return EventSourceResponse(_wrapped_generator())


def _make_event(event: PipelineEvent) -> dict[str, Any]:
    """Convert a PipelineEvent to an SSE event dictionary."""
    return {
        "event": event.stage,
        "data": json.dumps(
            {
                "type": event.stage,
                "status": event.status,
                "timestamp": datetime.now(UTC).isoformat(),
                **event.payload,
            },
            default=str,
        ),
    }


@router.get("/briefs/{session_id}", response_model=BriefResponse)
async def get_brief(
    session_id: str,
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
) -> BriefResponse:
    """Retrieve a generated brief by session ID."""
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
    config: Annotated[ConfigurationPort, Depends(get_config)],
) -> HealthResponse:
    """Health check endpoint."""
    providers = list(config.app_config.llm_providers.keys())

    return HealthResponse(
        status="ok",
        version=config.app_config.app_version,
        providers=providers,
    )
