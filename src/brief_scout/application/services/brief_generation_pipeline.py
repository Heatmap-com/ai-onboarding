"""Brief generation pipeline — orchestrates intake, research, and synthesis.

This service removes pipeline orchestration from the HTTP layer. It yields
domain PipelineEvent objects; the interface layer converts these to SSE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.application.services.research_pipeline import PipelineEvent
from brief_scout.domain.models.intake import Status

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from brief_scout.application.services.research_pipeline import (
        ResearchPipeline,
    )
    from brief_scout.application.use_cases.intake_use_case import IntakeUseCase
    from brief_scout.application.use_cases.synthesis_use_case import SynthesisUseCase
    from brief_scout.domain.models.intake import ChatSession
    from brief_scout.domain.ports.storage_port import BriefStoragePort


class BriefGenerationPipeline:
    """End-to-end pipeline: intake → research → synthesis → complete.

    Args:
        intake_use_case: Processes user messages and extracts intake data.
        research_pipeline: Runs the research calls.
        synthesis_use_case: Combines intake + research into a Brief.
        storage: Persists sessions and briefs.
    """

    def __init__(
        self,
        intake_use_case: IntakeUseCase,
        research_pipeline: ResearchPipeline,
        synthesis_use_case: SynthesisUseCase,
        storage: BriefStoragePort,
    ) -> None:
        self._intake_use_case = intake_use_case
        self._research_pipeline = research_pipeline
        self._synthesis_use_case = synthesis_use_case
        self._storage = storage

    async def run(
        self,
        session: ChatSession,
        user_message: str,
    ) -> AsyncIterator[PipelineEvent]:
        """Run the full pipeline and yield progress events."""
        # Intake
        intake_result = await self._intake_use_case.process_message(
            session,
            user_message,
        )
        yield PipelineEvent(
            stage="intake",
            status="complete",
            payload={
                "message": intake_result.assistant_message,
                "is_complete": intake_result.is_complete,
                "session_id": session.session_id,
                "status": intake_result.updated_session.status.value,
                "extracted_data": intake_result.extracted_data.model_dump(),
            },
        )

        if not intake_result.is_complete:
            return

        # Research
        async for event in self._research_pipeline.stream(intake_result.extracted_data):
            yield event

        # Synthesis
        yield PipelineEvent(stage="synthesis", status="started", payload={})

        brief = await self._synthesis_use_case.execute(
            intake_result.extracted_data,
            await self._research_pipeline.execute(intake_result.extracted_data),
        )
        await self._storage.save_brief(session.session_id, brief)

        session.status = Status.COMPLETE
        await self._storage.save_session(session)

        yield PipelineEvent(stage="synthesis", status="complete", payload={})

        # Final brief
        yield PipelineEvent(
            stage="brief",
            status="complete",
            payload={
                "brief": brief.model_dump(),
                "markdown": brief.to_markdown(),
                "session_id": session.session_id,
            },
        )

        yield PipelineEvent(
            stage="complete",
            status="complete",
            payload={"session_id": session.session_id},
        )
