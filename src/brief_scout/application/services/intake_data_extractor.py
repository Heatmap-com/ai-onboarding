"""Intake data extractor — extracts structured IntakeData from conversation history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brief_scout.domain.errors import BriefScoutError, LLMCallError
from brief_scout.domain.models import ChatMessage, IntakeData

if TYPE_CHECKING:
    from brief_scout.domain.models.journey import IntakeJourney
    from brief_scout.domain.ports.application_ports import (
        LoggerPort,
        StructuredCompletionPort,
        TemplateRenderer,
    )
    from brief_scout.domain.ports.provider_config_source_port import (
        ProviderConfigSource,
    )


class IntakeDataExtractor:
    """Extract structured intake data from a conversation using an LLM.

    This collaborator is responsible for building the extraction prompt,
    calling the LLM, and parsing the result. It keeps provider-specific
    configuration details (e.g., ``demo_turn``) out of ``IntakeUseCase``.
    """

    def __init__(
        self,
        llm: StructuredCompletionPort,
        journey: IntakeJourney,
        renderer: TemplateRenderer | None = None,
        provider_config_source: ProviderConfigSource | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            llm: Narrow LLM port for structured completions.
            journey: Declarative intake journey schema.
            renderer: Optional template renderer for prompt building.
            provider_config_source: Source for provider-specific extras.
            logger: Optional logger for diagnostics.
        """
        self._llm = llm
        self._journey = journey
        self._renderer = renderer
        self._provider_config_source = provider_config_source
        self._logger = logger

    async def extract(
        self,
        messages: list[ChatMessage],
        extraction_system: str,
    ) -> IntakeData:
        """Extract ``IntakeData`` from the conversation history.

        Args:
            messages: Full conversation history.
            extraction_system: System prompt for the extraction LLM call.

        Returns:
            Parsed IntakeData from the conversation.

        Raises:
            LLMCallError: If the LLM call or parsing fails.
        """
        self._log("Extracting structured data from conversation", level="DEBUG")

        prompt = self._build_prompt(extraction_system, messages)
        config = self._generic_extraction_config(messages)

        try:
            result = await self._llm.complete_structured(
                prompt,
                IntakeData,
                config=config,
            )
            self._log(
                "Structured data extraction successful",
                level="DEBUG",
                brand_name=result.brand_name,
                competitors_count=len(result.competitors),
            )
            return result
        except BriefScoutError:
            raise
        except Exception as exc:
            self._log(f"Structured extraction failed: {exc}", level="ERROR")
            raise LLMCallError(
                message=f"Failed to extract structured intake data: {exc}",
                provider=self._llm.provider_name,
            ) from exc

    def _build_prompt(
        self,
        extraction_system: str,
        messages: list[ChatMessage],
    ) -> Any:
        """Build the extraction prompt."""
        from brief_scout.application.services.intake_prompt_builder import (
            IntakePromptBuilder,
        )

        builder = IntakePromptBuilder(renderer=self._renderer)
        return builder.build_extraction_prompt(
            extraction_system,
            self._journey,
            messages,
        )

    def _generic_extraction_config(
        self,
        messages: list[ChatMessage],
    ) -> dict[str, Any] | None:
        """Return generic provider extras for the LLM port.

        The application layer no longer builds FakeLLM-specific ``demo_turn``
        config; it delegates to whatever extra configuration the active
        provider exposes. When a ``demo_journey_path`` extra is present, the
        current user turn number is appended so demo adapters can select the
        cumulative fixture without the use case knowing the adapter type.
        """
        if self._provider_config_source is None:
            return None

        try:
            provider_config = self._provider_config_source.get_provider_config(
                self._llm.provider_name,
            )
            extras = dict(provider_config.extras)
            if extras.get("demo_journey_path"):
                user_turns = sum(1 for msg in messages if msg.role == "user")
                extras["demo_turn"] = user_turns
            return extras if extras else None
        except KeyError:
            return None

    def _log(self, message: str, level: str = "INFO", **kwargs: Any) -> None:
        if self._logger is not None:
            self._logger.log(message, level=level, **kwargs)
