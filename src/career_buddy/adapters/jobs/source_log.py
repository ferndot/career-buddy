"""Log lines per source, kept in memory for the Sources screen. shortcut: lost on restart, like the job state."""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime
from itertools import count
from typing import Any

from career_buddy.application.activity import current_source

MAX_LINES = 500
MAX_MESSAGE = 600


class SourceLog:
    """The last `max_lines` lines of each source's latest run. `seq` grows across all sources, so a client's cursor survives a new run."""

    def __init__(self, max_lines: int = MAX_LINES) -> None:
        self._max = max_lines
        self._lines: dict[str, deque[dict[str, Any]]] = {}
        self._runs: dict[str, int] = {}
        self._seq = count(1)

    def start(self, source: str) -> None:
        """A new run: the earlier lines go."""
        self._lines[source] = deque(maxlen=self._max)
        self._runs[source] = self._runs.get(source, 0) + 1

    def add(self, source: str, level: str, logger: str, message: str, when: datetime | None = None) -> None:
        lines = self._lines.setdefault(source, deque(maxlen=self._max))
        lines.append({"seq": next(self._seq), "time": (when or datetime.now(UTC)).isoformat(), "level": level,
                      "logger": logger, "message": message[:MAX_MESSAGE]})

    def drop(self, source: str) -> None:
        self._lines.pop(source, None)
        self._runs.pop(source, None)

    def read(self, source: str, since: int = 0) -> dict[str, Any]:
        """Lines after the cursor `since`, the new cursor, and the run number (a changed run means: discard what you hold)."""
        lines = [line for line in self._lines.get(source, ()) if line["seq"] > since]
        return {"lines": lines, "cursor": lines[-1]["seq"] if lines else since, "run": self._runs.get(source, 0)}


class SourceLogHandler(logging.Handler):
    """Files each record under the source being processed (see application.activity); other records are ignored."""

    def __init__(self, log: SourceLog) -> None:
        super().__init__(logging.INFO)
        self._log = log

    def emit(self, record: logging.LogRecord) -> None:
        source = current_source.get()
        if source is None:
            return
        try:
            self._log.add(source, record.levelname, record.name, record.getMessage(), datetime.fromtimestamp(record.created, UTC))
        except Exception:
            self.handleError(record)
