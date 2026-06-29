"""JSONL writer — responsible for daily JSON Lines file I/O."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import aiofiles


class JsonlWriter:
    """Writes JSON objects as lines to a daily log file."""

    def __init__(self, log_dir: str | Path) -> None:
        """Initialize the writer.

        Args:
            log_dir: Directory where log files are written.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    async def write(self, entry: dict[str, Any]) -> None:
        """Write a single entry to the current day's log file.

        Args:
            entry: Structured log entry dictionary.
        """
        log_file = self._log_dir / f"brief_scout_{date.today().isoformat()}.jsonl"
        try:
            async with aiofiles.open(log_file, "a", encoding="utf-8") as f:
                await f.write(json.dumps(entry, default=str) + "\n")
        except OSError as exc:
            print(f"Failed to write log entry: {exc}", file=sys.stderr)
