"""Research pipeline — executes a configurable sequence of research steps."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from brief_scout.domain.models.research import ResearchBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from brief_scout.domain.models.intake import IntakeData
    from brief_scout.domain.ports.telemetry_port import TelemetryPort


class PipelineEvent(BaseModel):
    """Domain event emitted by pipeline stages."""

    stage: str = ""
    status: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ResearchStep(Protocol):
    """A single pluggable research step."""

    name: str

    async def execute(self, intake_data: IntakeData) -> BaseModel:
        """Execute the step and return a typed result."""
        ...


class ResearchPipeline:
    """Runs a sequence of ``ResearchStep`` instances concurrently.

    Failures in individual steps are caught and returned as default empty
    results so the overall pipeline always produces a ``ResearchBundle``.
    """

    def __init__(
        self,
        steps: Sequence[ResearchStep],
        telemetry: TelemetryPort | None = None,
        max_concurrent_calls: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize the pipeline with a sequence of steps.

        Args:
            steps: Research steps to execute.
            telemetry: Optional telemetry port for logging and events.
            max_concurrent_calls: Optional semaphore limit for concurrent steps.
            timeout_seconds: Optional per-step timeout.
        """
        self._steps = list(steps)
        self._telemetry = telemetry
        self._last_bundle: ResearchBundle | None = None
        self._semaphore = asyncio.Semaphore(max_concurrent_calls) if max_concurrent_calls else None
        self._timeout = timeout_seconds

    @property
    def last_bundle(self) -> ResearchBundle | None:
        """The bundle produced by the most recent ``stream`` or ``execute``."""
        return self._last_bundle

    async def execute(self, intake_data: IntakeData) -> ResearchBundle:
        """Run all steps concurrently and return a populated ``ResearchBundle``."""
        results: dict[str, BaseModel] = {}

        coroutines = [self._run_step(step, intake_data) for step in self._steps]
        step_results = await asyncio.gather(*coroutines, return_exceptions=True)

        for step, outcome in zip(self._steps, step_results, strict=True):
            if isinstance(outcome, BaseException):
                self._log_failure(step.name, outcome)
                continue
            results[step.name] = outcome

        self._last_bundle = ResearchBundle(
            results=results,
            completed_at=datetime.now(UTC),
        )
        return self._last_bundle

    async def stream(
        self,
        intake_data: IntakeData,
    ) -> AsyncIterator[PipelineEvent]:
        """Execute steps concurrently, yielding progress events.

        Yields a ``started`` event, one event per step completion/failure,
        and a ``complete`` event.
        """
        yield PipelineEvent(
            stage="research",
            status="started",
            payload={"steps": [step.name for step in self._steps]},
        )

        coroutines = [self._run_step(step, intake_data) for step in self._steps]
        step_results = await asyncio.gather(*coroutines, return_exceptions=True)

        results: dict[str, BaseModel] = {}
        for step, outcome in zip(self._steps, step_results, strict=True):
            if isinstance(outcome, BaseException):
                self._log_failure(step.name, outcome)
                yield PipelineEvent(
                    stage="research_step",
                    status="failed",
                    payload={"name": step.name, "error": str(outcome)},
                )
            else:
                results[step.name] = outcome
                yield PipelineEvent(
                    stage="research_step",
                    status="complete",
                    payload={"name": step.name},
                )

        self._last_bundle = ResearchBundle(
            results=results,
            completed_at=datetime.now(UTC),
        )
        yield PipelineEvent(stage="research", status="complete")

    async def _run_step(
        self,
        step: ResearchStep,
        intake_data: IntakeData,
    ) -> BaseModel:
        """Run a single step under the configured concurrency/timeout limits."""
        self._log("DEBUG", f"Research step starting: {step.name}", step_name=step.name)
        if self._semaphore is not None:
            async with self._semaphore:
                result = await self._execute(step, intake_data)
        else:
            result = await self._execute(step, intake_data)
        self._log("DEBUG", f"Research step complete: {step.name}", step_name=step.name)
        return result

    async def _execute(
        self,
        step: ResearchStep,
        intake_data: IntakeData,
    ) -> BaseModel:
        """Execute a single step with an optional timeout."""
        coro = step.execute(intake_data)
        if self._timeout is not None:
            return await asyncio.wait_for(coro, timeout=self._timeout)
        return await coro

    def _log_failure(self, step_name: str, exc: BaseException) -> None:
        """Log a step failure via telemetry."""
        self._log(
            "ERROR",
            f"Research step failed: {step_name} — {exc}",
            step_name=step_name,
            error=str(exc),
        )

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        if self._telemetry is not None:
            self._telemetry.log(message, level=level, **kwargs)
