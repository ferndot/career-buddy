"""Processing state of sources. Services report progress here; the web layer only reads it."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from career_buddy.application.activity import current_source
from career_buddy.application.ports import JobState, JobStore, LLMUnavailable, SourceBusy, UnreadableDocument

log = logging.getLogger(__name__)
ACTIVE = ("queued", "processing")
READY = JobState("ready", 100, "Done")


def user_message(error: Exception) -> str:
    """Only errors whose text is safe by design are shown; anything else gets a generic line (no traceback, URL or key)."""
    if isinstance(error, LLMUnavailable | UnreadableDocument):
        return str(error)
    return "Extraction failed unexpectedly. Try again."


class SourceJobs:
    def __init__(self, store: JobStore, on_start: Callable[[str], None] = lambda source: None) -> None:
        self._store = store
        self._on_start = on_start  # a new run of a source begins (the log of the earlier run can go)
        self._tasks: set[asyncio.Task[None]] = set()  # strong references, or a running task can be collected

    def state(self, source: str) -> JobState | None:
        return self._store.get(source)

    def states(self) -> dict[str, JobState]:
        return self._store.all()

    def forget(self, source: str) -> None:
        self._store.delete(source)

    def is_active(self, source: str) -> bool:
        state = self._store.get(source)
        return state is not None and state.status in ACTIVE

    def report(self, source: str, step: str, progress: int) -> None:
        self._store.put(source, JobState("processing", progress, step))
        log.info("%s (%d%%)", step, progress)

    async def _guarded(self, source: str, work: Callable[[], Awaitable[Any]]) -> Any:
        token = current_source.set(source)  # log lines of this work (and the tasks it starts) belong to the source
        try:
            log.info("Processing started")
            result = await work()
        except Exception as error:
            log.warning("Processing %s failed: %s", source, type(error).__name__)
            self._store.put(source, JobState("failed", 0, "Failed", user_message(error)))
            raise
        else:
            log.info("Processing finished")
            self._store.put(source, READY)
            return result
        finally:
            current_source.reset(token)

    async def run(self, source: str, work: Callable[[], Awaitable[Any]], background: bool) -> Any:
        """Mark the source queued, then run `work` (which reports progress). Background: return None at once.
        Foreground: return the result, and on error drop the entry and re-raise so the caller can answer it."""
        if self.is_active(source):
            raise SourceBusy(source)
        self._on_start(source)
        self._store.put(source, JobState("queued", 0, "Queued"))
        if not background:
            try:
                return await self._guarded(source, work)
            except Exception:
                self._store.delete(source)
                raise

        async def task() -> None:
            try:
                await self._guarded(source, work)
            except Exception:
                pass  # already recorded as failed

        handle = asyncio.create_task(task())
        self._tasks.add(handle)
        handle.add_done_callback(self._tasks.discard)
        return None
