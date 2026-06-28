"""Jinja2-based template renderer adapter."""

from __future__ import annotations

from typing import Any

from jinja2 import Template


class Jinja2TemplateRenderer:
    """Renders templates using Jinja2.

    This adapter keeps Jinja2 in the infrastructure layer and out of the
    domain/application models.
    """

    def render(self, template: str, context: dict[str, Any] | None = None) -> str:
        """Render a template string against the provided context.

        Args:
            template: The template string to render.
            context: Variables available during rendering.

        Returns:
            The rendered string.
        """
        ctx = context or {}
        return Template(template).render(**ctx)
