"""Shared JSON utilities for LLM adapters."""

from __future__ import annotations

import json


def strip_markdown_code_blocks(content: str) -> str:
    """Remove markdown code fences from JSON content."""
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def safe_json_loads(content: str) -> dict[str, object] | None:
    """Attempt to parse a JSON object from content.

    Returns:
        Parsed dict on success, None on failure.
    """
    try:
        parsed = json.loads(strip_markdown_code_blocks(content))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
