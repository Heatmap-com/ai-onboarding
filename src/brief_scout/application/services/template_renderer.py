"""Template renderer implementations for the ``TemplateRenderer`` port.

This module lives in the application layer because it adapts a third-party
rendering library to the domain port. Agent 2 may later move the Jinja2
implementation into the infrastructure layer and inject it at the
composition root.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Template

from brief_scout.domain.ports.application_ports import TemplateRenderer


class Jinja2TemplateRenderer(TemplateRenderer):
    """Renders templates using Jinja2."""

    def render(self, template: str, context: dict[str, Any]) -> str:
        """Render ``template`` with ``context`` using Jinja2."""
        return Template(template).render(**context)
