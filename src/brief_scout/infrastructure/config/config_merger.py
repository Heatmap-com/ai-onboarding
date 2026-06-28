"""Config merger — responsible for deep-merging configuration dictionaries."""

from __future__ import annotations

from typing import Any


class ConfigMerger:
    """Recursively merges configuration overlays onto a base dictionary."""

    def merge(self, base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge overlay onto base.

        For each key in overlay:
        - If both values are dicts, merge recursively.
        - Otherwise, overlay value replaces base value.

        Args:
            base: The base dictionary.
            overlay: The overlay dictionary.

        Returns:
            A new dictionary with merged values.
        """
        result = dict(base)
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge(result[key], value)
            else:
                result[key] = value
        return result
