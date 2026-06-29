"""End-to-end brief generation pipeline.

Orchestrates intake → research → synthesis → brief persistence and emits
domain progress events. The interface layer can wrap these events in SSE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from brief_scout.application.services.brief_markdown_renderer import (
    BriefMarkdownRenderer,
)
from brief_scout.domain.models.intake import Status
from brief_scout.domain.ports.pipeline_event import PipelineEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from brief_scout.domain.models import ChatSession
    from brief_scout.domain.ports import (
        BriefStoragePort,
        IntakePort,
        ResearchPipelinePort,
        SynthesisPort,
    )
    from brief_scout.domain.ports.completeness_port import CompletenessCheckPort


class _BackwardCompatibleCompletenessChecker(BaseModel):
    """Temporary fallback preserving the old ``IntakeData.is_complete()`` behavior.

    TODO(integration): Remove this helper once ``main.py`` injects the domain
    ``CompletenessChecker`` into ``BriefGenerationPipeline``.
    """

    def check(self, intake_data: Any) -> Any:
        from brief_scout.domain.models.intake import IntakeData

        data = IntakeData.model_validate(intake_data)
        is_complete = bool(
            data.brand_name and data.competitors and data.primary_goal and data.target_customer
        )
        return type(
            "CompletenessResult",
            (),
            {"is_complete": is_complete},
        )()


class BriefGenerationPipeline:
    """Runs the full brief generation flow and yields domain events."""

    def __init__(
        self,
        intake_use_case: IntakePort,
        research_pipeline: ResearchPipelinePort,
        synthesis_use_case: SynthesisPort,
        storage: BriefStoragePort,
        completeness_checker: CompletenessCheckPort | None = None,
    ) -> None:
        """Initialize the pipeline with injected use cases and storage.

        Args:
            intake_use_case: Intake processing use case.
            research_pipeline: Research execution pipeline.
            synthesis_use_case: Brief synthesis use case.
            storage: Storage port for persisting sessions and briefs.
            completeness_checker: Optional completeness checker. If omitted, a
                backward-compatible checker is used until the integration wave
                wires the domain checker.
        """
        self._intake = intake_use_case
        self._research = research_pipeline
        self._synthesis = synthesis_use_case
        self._storage = storage
        self._completeness_checker = (
            completeness_checker or _BackwardCompatibleCompletenessChecker()
        )

    async def run(
        self,
        session: ChatSession,
        user_message: str | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        """Yield progress events for intake, research, synthesis, and completion.

        Args:
            session: Current chat session.
            user_message: Optional user message. When ``None``, the pipeline
                resumes from the existing session state (used by the idempotent
                ``POST /pipeline`` endpoint).
        """
        try:
            extracted_data = session.intake_data
            assistant_message = ""
            intake_complete = False

            if user_message is not None:
                # ─── INTAKE ───
                intake_result = await self._intake.process_message(session, user_message)
                extracted_data = intake_result.extracted_data
                assistant_message = intake_result.assistant_message
                intake_complete = intake_result.is_complete
                yield PipelineEvent(
                    stage="intake",
                    status="complete",
                    payload={
                        "message": assistant_message,
                        "is_complete": intake_complete,
                        "session_id": session.session_id,
                        "status": session.status.value,
                        "extracted_data": extracted_data.model_dump(),
                    },
                )

                if not intake_complete:
                    return
            else:
                # Resuming from existing session state.
                if not self._completeness_checker.check(session.intake_data).is_complete:
                    yield PipelineEvent(
                        stage="intake",
                        status="progress",
                        payload={
                            "message": assistant_message,
                            "is_complete": False,
                            "session_id": session.session_id,
                            "status": session.status.value,
                            "extracted_data": extracted_data.model_dump(),
                        },
                    )
                    return
                intake_complete = True

            # ─── RESEARCH ───
            if session.status != Status.RESEARCHING:
                session.status = Status.RESEARCHING
                await self._storage.save_session(session)

            async for event in self._research.stream(extracted_data):
                # Forward per-step events so consumers can track individual steps.
                stage = event.stage if event.stage == "research_step" else "research"
                yield PipelineEvent(
                    stage=stage,
                    status=_map_research_status(event.status),
                    payload=event.payload,
                )

            research_bundle = self._research.last_bundle or await self._research.execute(
                extracted_data,
            )

            # ─── SYNTHESIS ───
            yield PipelineEvent(stage="synthesis", status="started")
            try:
                brief = await self._synthesis.execute(
                    extracted_data,
                    research_bundle,
                )
            except Exception as exc:  # noqa: BLE001
                session.status = Status.FAILED
                await self._storage.save_session(session)
                yield PipelineEvent(
                    stage="synthesis",
                    status="failed",
                    payload={
                        "error": str(exc),
                        "session_id": session.session_id,
                        "recoverable": True,
                    },
                )
                return

            await self._storage.save_brief(session.session_id, brief)
            yield PipelineEvent(stage="synthesis", status="complete")

            # ─── BRIEF ───
            yield PipelineEvent(
                stage="brief",
                status="complete",
                payload={
                    "brief": brief.model_dump(),
                    "markdown": BriefMarkdownRenderer().render(brief),
                    "session_id": session.session_id,
                },
            )

            # ─── COMPLETE ───
            session.status = Status.COMPLETE
            await self._storage.save_session(session)
            yield PipelineEvent(
                stage="complete",
                status="complete",
                payload={"session_id": session.session_id},
            )

        except Exception as exc:
            session.status = Status.FAILED
            await self._storage.save_session(session)
            yield PipelineEvent(
                stage="complete",
                status="failed",
                payload={
                    "error": str(exc),
                    "session_id": session.session_id,
                },
            )


def _map_research_status(status: str) -> Literal["started", "progress", "complete", "failed"]:
    """Map research pipeline event status to brief pipeline status."""
    if status == "started":
        return "started"
    if status == "complete":
        return "complete"
    if status == "failed":
        return "failed"
    return "progress"
