"""Environment variable interpolator — replaces ${VAR} placeholders."""

from __future__ import annotations

import os
import re
from typing import Any


class EnvInterpolator:
    """Recursively interpolates ``${VAR_NAME}`` placeholders with env vars."""

    _ENV_VAR_PATTERN: re.Pattern[str] = re.compile(r"\$\{([^}]+)\}")

    def interpolate(self, obj: Any) -> Any:
        """Recursively interpolate ``${VAR_NAME}`` placeholders.

        Args:
            obj: The object to interpolate (str, list, dict, or other).

        Returns:
            The interpolated object with the same structure.
        """
        if isinstance(obj, str):
            return self._replace_env_vars(obj)
        if isinstance(obj, dict):
            return {k: self.interpolate(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.interpolate(item) for item in obj]
        return obj

    def _replace_env_vars(self, text: str) -> str:
        """Replace ``${VAR_NAME}`` patterns with env var values.

        Args:
            text: The string potentially containing placeholders.

        Returns:
            The string with placeholders replaced (or left unchanged if unset).
        """

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return self._ENV_VAR_PATTERN.sub(replacer, text)
