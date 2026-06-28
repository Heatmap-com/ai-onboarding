"""Reloadable config port — contract for configuration hot-reloading."""

from __future__ import annotations

from typing import Protocol


class ReloadableConfig(Protocol):
    """Port for configurations that support hot-reloading."""

    def reload(self) -> None:
        """Reload configuration from source.

        The contract is eager: after this method returns, the next read
        must reflect the latest source state. Implementations may clear
        caches or re-read files immediately. Any source errors propagate
        as ConfigError or a subclass.
        """
        ...
