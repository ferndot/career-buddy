"""The live log of a source's processing, read by the Sources screen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter

from career_buddy.adapters.jobs.source_log import SourceLog
from career_buddy.application.ports import SourceNotFound


def source_log_router(log: SourceLog, sources: Callable[[], Awaitable[list[dict[str, object]]]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sources/{source}/log")
    async def source_log(source: str, since: int = 0) -> dict[str, object]:
        """New lines after the cursor `since`, plus the source's status, so one poll shows both."""
        record = next((s for s in await sources() if s["source"] == source), None)
        if record is None:
            raise SourceNotFound(source)
        return {**log.read(source, since), **{k: record[k] for k in ("status", "progress", "step", "error")}}

    return router
