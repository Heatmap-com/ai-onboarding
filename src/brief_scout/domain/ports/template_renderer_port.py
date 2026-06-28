"""Template renderer port — contract for rendering template strings."""

from __future__ import annotations

from typing import Any, Protocol


class TemplateRenderer(Protocol):
    """Port for rendering templates with variable substitution."""

    def render(self, template: str, context: dict[str, Any] | None = None) -> str:
        """Render a template string against the provided context.

        Args:
            template: The template string to render.
            context: Variables available during rendering.

        Returns:
            The rendered string.
        """
        ...
