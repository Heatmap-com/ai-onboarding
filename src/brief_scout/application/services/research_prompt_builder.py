"""Builds prompts for individual research steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brief_scout.domain.ports import Prompt

if TYPE_CHECKING:
    from brief_scout.domain.models.config import PromptTemplateConfig


class ResearchPromptBuilder:
    """Builds a research prompt from a template and variable dictionary.

    Templates use ``{variable_name}`` placeholders (plain braces) so they can
    be authored without Jinja2 knowledge. The builder substitutes each
    placeholder with its string value.
    """

    def build(self, template: PromptTemplateConfig, variables: dict[str, str]) -> Prompt:
        """Return a ``Prompt`` with substituted variables.

        Args:
            template: The prompt template config.
            variables: Mapping of placeholder names to replacement strings.

        Returns:
            A formatted ``Prompt``.
        """
        user_content = template.user
        for key, value in variables.items():
            user_content = user_content.replace("{" + key + "}", value)

        return Prompt(
            system=template.system,
            user=user_content,
        )
