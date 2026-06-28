"""End-to-end brief generation pipeline.

Orchestrates intake → research → synthesis → brief persistence and emits
domain progress events. The interface layer can wrap these events in SSE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from brief_scout.domain.models.intake import Status

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from brief_scout.application.services.research_pipeline import ResearchPipeline
    from brief_scout.application.use_cases.intake_use_case import IntakeUseCase
    from brief_scout.application.use_cases.synthesis_use_case import SynthesisUseCase
    from brief_scout.domain.models import ChatSession
    from brief_scout.domain.ports.storage_port import BriefStoragePort


class PipelineEvent(BaseModel):
    """Domain event emitted by the brief generation pipeline."""

    stage: Literal["intake", "research", "synthesis", "complete"] = "intake"
    status: Literal["started", "progress", "complete", "failed"] = "progress"
    payload: dict[str, Any] = Field(default_factory=dict)


class BriefGenerationPipeline:
    """Runs the full brief generation flow and yields domain events."""

    def __init__(
        self,
        intake_use_case: IntakeUseCase,
        research_pipeline: ResearchPipeline,
        synthesis_use_case: SynthesisUseCase,
        storage: BriefStoragePort,
    ) -> None:
        """Initialize the pipeline with injected use cases and storage.

        Args:
            intake_use_case: Intake processing use case.
            research_pipeline: Research execution pipeline.
            synthesis_use_case: Brief synthesis use case.
            storage: Storage port for persisting sessions and briefs.
        """
        self._intake = intake_use_case
        self._research = research_pipeline
        self._synthesis = synthesis_use_case
        self._storage = storage

    async def run(
        self,
        session: ChatSession,
        user_message: str,
    ) -> AsyncIterator[PipelineEvent]:
        """Yield progress events for intake, research, synthesis, and completion."""
        try:
            # ─── INTAKE ───
            intake_result = await self._intake.process_message(session, user_message)
            yield PipelineEvent(
                stage="intake",
                status="complete",
                payload={
                    "message": intake_result.assistant_message,
                    "is_complete": intake_result.is_complete,
                    "session_id": session.session_id,
                    "status": intake_result.updated_session.status.value,
                },
            )

            if not intake_result.is_complete:
                return

            # ─── RESEARCH ───
            async for event in self._research.stream(intake_result.extracted_data):
                yield PipelineEvent(
                    stage="research",
                    status=_map_research_status(event.status),
                    payload=event.payload,
                )

            research_bundle = await self._research.execute(intake_result.extracted_data)

            # ─── SYNTHESIS ───
            yield PipelineEvent(stage="synthesis", status="started")
            brief = await self._synthesis.execute(
                intake_result.extracted_data,
                research_bundle,
            )
            await self._storage.save_brief(session.session_id, brief)
            yield PipelineEvent(stage="synthesis", status="complete")

            # ─── COMPLETE ───
            session.status = Status.COMPLETE
            await self._storage.save_session(session)
            yield PipelineEvent(
                stage="complete",
                status="complete",
                payload={
                    "brief": brief.model_dump(),
                    "session_id": session.session_id,
                },
            )

        except Exception as exc:
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
