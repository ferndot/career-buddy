"""POST /api/chat: the career chat as an AG-UI event stream. The body is the AG-UI RunAgentInput; the chat keeps nothing between requests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent, RunStartedEvent
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from career_buddy.application.chat_tools import ChatTools

NO_MODEL = "Connect a model in Settings to chat about your career."


async def no_model(input: RunAgentInput) -> AsyncIterator[BaseEvent]:
    yield RunStartedEvent(thread_id=input.thread_id, run_id=input.run_id)
    yield RunErrorEvent(message=NO_MODEL, code="no_model")


def chat_router(chat: Callable[[], Any], tools: Callable[[], ChatTools]) -> APIRouter:
    """`chat` returns the active connection's GraphCareerChat, or None when no model is connected; it is read at each request."""
    router = APIRouter()

    @router.post("/api/chat")
    async def post_chat(input: RunAgentInput) -> StreamingResponse:
        encoder, model = EventEncoder(), chat()

        async def stream() -> AsyncIterator[str]:
            async for event in (model.run(input, tools()) if model else no_model(input)):
                yield encoder.encode(event)

        return StreamingResponse(stream(), media_type=encoder.get_content_type(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
