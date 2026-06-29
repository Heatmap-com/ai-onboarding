"""FastAPI routes with Server-Sent Events (SSE) streaming.

Per SPEC 8.1 — Provides REST endpoints for chat sessions, message
exchange, brief retrieval, and health checks.

Endpoints:
    POST /api/v1/chat/sessions                 — Create a new chat session
    POST /api/v1/chat/{session_id}/message     — Send message; returns JSON
                                                 while intake is incomplete and
                                                 streams the full pipeline once
                                                 intake becomes complete.
    POST /api/v1/chat/{session_id}/pipeline    — Idempotent pipeline run
    GET  /api/v1/briefs/{session_id}           — Retrieve a generated brief
    GET  /api/v1/health                        — Health check
"""

from __future__ import annotations

import asyncio
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
from brief_scout.application.services.brief_markdown_renderer import (  # noqa: TC001
    BriefMarkdownRenderer,
)
from brief_scout.domain.models import ChatSession
from brief_scout.domain.ports.config_port import ConfigurationPort  # noqa: TC001
from brief_scout.domain.ports.pipeline_port import PipelinePort  # noqa: TC001
from brief_scout.domain.ports.storage_port import BriefStoragePort  # noqa: TC001
from brief_scout.interfaces.api.dependencies import (
    get_brief_markdown_renderer,
    get_config,
    get_pipeline,
    get_storage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from brief_scout.application.services.brief_markdown_renderer import (
        BriefMarkdownRenderer,
    )

router = APIRouter(prefix="/api/v1")

# Per-session locks so the idempotent pipeline endpoint can reject concurrent
# runs without blocking the event loop.
_pipeline_locks: dict[str, asyncio.Lock] = {}


def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Return (and create if needed) a lock for the given session."""
    if session_id not in _pipeline_locks:
        _pipeline_locks[session_id] = asyncio.Lock()
    return _pipeline_locks[session_id]


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


@router.post("/chat/{session_id}/message", response_model=None)
async def send_message(
    session_id: str,
    request_body: MessageRequest,
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
    pipeline: Annotated[PipelinePort, Depends(get_pipeline)],
) -> ChatResponse | EventSourceResponse:
    """Send a message and run the pipeline.

    While intake is incomplete, returns a JSON ``ChatResponse`` so the client
    can continue the conversation. Once intake becomes complete, the response
    switches to an SSE stream of the full pipeline (research, synthesis, brief).
    """
    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    generator = pipeline.run(session, request_body.message)

    # Consume the intake event to decide how to respond.
    first_event = await generator.__anext__()
    if first_event.stage != "intake":
        # Defensive: if the pipeline yields something else, just stream it.
        async def _resume_from(event: PipelineEvent) -> AsyncGenerator[dict[str, Any], None]:
            yield _make_event(event)
            async for event in generator:
                yield _make_event(event)

        return EventSourceResponse(_resume_from(first_event))

    if not first_event.payload.get("is_complete"):
        # Intake still in progress — return a normal JSON response.
        return ChatResponse(
            message=first_event.payload.get("message", ""),
            session_id=session_id,
            status=session.status,
            extracted_data=first_event.payload.get("extracted_data", {}),
        )

    # Intake complete — stream the rest of the pipeline (including the intake
    # event so the client still sees the assistant's completion message).
    async def _stream_pipeline() -> AsyncGenerator[dict[str, Any], None]:
        try:
            yield _make_event(first_event)
            async for event in generator:
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

    return EventSourceResponse(_stream_pipeline())


@router.post("/chat/{session_id}/pipeline")
async def run_pipeline(
    session_id: str,
    storage: Annotated[BriefStoragePort, Depends(get_storage)],
    pipeline: Annotated[PipelinePort, Depends(get_pipeline)],
    renderer: Annotated[BriefMarkdownRenderer, Depends(get_brief_markdown_renderer)],
) -> EventSourceResponse:
    """Idempotent pipeline endpoint.

    Accepts only a session ID. If a brief already exists, returns a ``brief``
    event immediately. If intake is incomplete, returns an ``intake`` event and
    stops. If the pipeline is already running for this session, returns a
    ``pipeline_busy`` error event.
    """
    session = await storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    existing_brief = await storage.get_brief(session_id)
    if existing_brief is not None:

        async def _brief_only() -> AsyncGenerator[dict[str, Any], None]:
            yield _make_event(
                PipelineEvent(
                    stage="brief",
                    status="complete",
                    payload={
                        "brief": existing_brief.model_dump(),
                        "markdown": renderer.render(existing_brief),
                        "session_id": session_id,
                    },
                )
            )

        return EventSourceResponse(_brief_only())

    lock = _get_session_lock(session_id)
    if lock.locked():

        async def _busy() -> AsyncGenerator[dict[str, Any], None]:
            yield _make_event(
                PipelineEvent(
                    stage="pipeline_busy",
                    status="failed",
                    payload={
                        "message": "Pipeline is already running for this session",
                        "recoverable": True,
                        "session_id": session_id,
                    },
                )
            )

        return EventSourceResponse(_busy())

    await lock.acquire()

    async def _wrapped_generator() -> AsyncGenerator[dict[str, Any], None]:
        try:
            async for event in pipeline.run(session):
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
        finally:
            lock.release()

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
    renderer: Annotated[BriefMarkdownRenderer, Depends(get_brief_markdown_renderer)],
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
        markdown=renderer.render(brief),
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
