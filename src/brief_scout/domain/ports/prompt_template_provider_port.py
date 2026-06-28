"""Prompt template provider port — lookup for prompt templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig


class PromptTemplateProvider(Protocol):
    """Port for retrieving prompt templates by name."""

    def get_prompt_template(self, template_name: str) -> PromptTemplateConfig:
        """Get a prompt template by name.

        Args:
            template_name: The template identifier.

        Returns:
            The PromptTemplateConfig with system and user strings.

        Raises:
            KeyError: If the template is not found.
        """
        ...
