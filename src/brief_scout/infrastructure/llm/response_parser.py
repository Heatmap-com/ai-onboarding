"""Structured response parser — strips fences and validates JSON against schema."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from brief_scout.domain.errors import LLMCallError
from brief_scout.infrastructure.llm.shared_json_utils import strip_markdown_code_blocks

T = TypeVar("T", bound=BaseModel)


class ResponseParser:
    """Parses raw LLM text into a validated Pydantic model."""

    def parse(self, content: str, output_schema: type[T], provider: str = "") -> T:
        """Strip markdown fences, parse JSON, and validate against the schema.

        Args:
            content: Raw text from the LLM.
            output_schema: Pydantic model class to validate against.
            provider: Provider identifier for error attribution.

        Returns:
            A validated instance of the output schema.

        Raises:
            LLMCallError: If JSON parsing or validation fails.
        """
        cleaned = strip_markdown_code_blocks(content)
        try:
            data = json.loads(cleaned)
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMCallError(
                f"Failed to parse structured output: {exc}",
                provider=provider,
                retryable=False,
                raw_content=content[:500],
            ) from exc
