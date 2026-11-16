"""Which source the running work belongs to. Log adapters read it to file a log line under the right source."""

from __future__ import annotations

from contextvars import ContextVar

current_source: ContextVar[str | None] = ContextVar("current_source", default=None)
