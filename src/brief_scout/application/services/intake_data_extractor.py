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
        renderer: TemplateRenderer,
        provider_config_source: ProviderConfigSource | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            llm: Narrow LLM port for structured completions.
            journey: Declarative intake journey schema.
            renderer: Template renderer for prompt building.
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
        max_retries: int = 1,
    ) -> IntakeData:
        """Extract ``IntakeData`` from the conversation history.

        Args:
            messages: Full conversation history.
            extraction_system: System prompt for the extraction LLM call.
            max_retries: Number of retries on parse/validation failures.

        Returns:
            Parsed IntakeData from the conversation.

        Raises:
            LLMCallError: If the LLM call or parsing fails after retries.
        """
        self._log("Extracting structured data from conversation", level="DEBUG")

        config = self._generic_extraction_config(messages)
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            prompt = self._build_prompt(extraction_system, messages, attempt=attempt)
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
                last_error = exc
                self._log(
                    f"Structured extraction failed (attempt {attempt + 1}): {exc}",
                    level="WARNING",
                )

        raise LLMCallError(
            message=f"Failed to extract structured intake data: {last_error}",
            provider=self._llm.provider_name,
        ) from last_error

    def _build_prompt(
        self,
        extraction_system: str,
        messages: list[ChatMessage],
        attempt: int = 0,
    ) -> Any:
        """Build the extraction prompt."""
        from brief_scout.application.services.intake_prompt_builder import (
            IntakePromptBuilder,
        )

        builder = IntakePromptBuilder(renderer=self._renderer)
        prompt = builder.build_extraction_prompt(
            extraction_system,
            self._journey,
            messages,
        )
        if attempt > 0:
            retry_note = (
                "\n\nImportant: your previous response did not match the required "
                "schema. Return only a valid JSON object that conforms exactly to the schema."
            )
            prompt = prompt.model_copy(update={"system": prompt.system + retry_note})
        return prompt

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
