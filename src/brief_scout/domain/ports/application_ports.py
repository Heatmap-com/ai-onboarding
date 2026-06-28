"""Local narrow protocols used by the domain/application layers.

These protocols are intentionally smaller than the official ports in
``brief_scout.domain.ports``. They let application services declare exactly
the capabilities they need. The integration engineer will reconcile them
with Agent 2's official narrow ports during merge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from brief_scout.domain.ports.telemetry_port import LogLevel

if TYPE_CHECKING:
    from brief_scout.domain.models.intake import ChatSession
    from brief_scout.domain.ports.llm_port import Prompt

T = TypeVar("T", bound=BaseModel)


class LoggerPort(Protocol):
    """Minimal logging dependency.

    Services that only need to emit structured log lines can depend on this
    narrow port instead of the full ``TelemetryPort``.
    """

    def log(
        self,
        message: str,
        level: LogLevel | str = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Log a structured message."""
        ...


class SessionWriter(Protocol):
    """Narrow port for persisting chat sessions.

    ``IntakeUseCase`` only needs to save sessions; it does not read them or
    store briefs.
    """

    async def save_session(self, session: ChatSession) -> None:
        """Persist ``session``."""
        ...


@runtime_checkable
class StructuredCompletionPort(Protocol):
    """Narrow LLM port for structured output only.

    Application use cases never call ``complete()``; they only need the
    structured completion path.
    """

    @property
    def provider_name(self) -> str:
        """Provider identifier, e.g. ``fake`` or ``openai``."""
        ...

    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
        config: dict[str, Any] | None = None,
    ) -> T:
        """Execute a structured completion and return a parsed model."""
        ...


class TemplateRenderer(Protocol):
    """Port for rendering string templates.

    Implementations may use Jinja2, Python ``str.format``, or any other
    templating engine. The application layer depends only on this contract.
    """

    def render(self, template: str, context: dict[str, Any]) -> str:
        """Render ``template`` using ``context``.

        Args:
            template: The template string.
            context: Mapping of variable names to values.

        Returns:
            The rendered string.
        """
        ...
