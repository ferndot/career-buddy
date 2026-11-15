"""HTTP routes for the LLM connections settings page. Keys come in here and never go back out."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from career_graph.adapters.inference.connections import LLMConnections


class ConnectionFields(BaseModel):
    preset: str | None = None
    label: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    allow_private: bool | None = None


class ConnectionCreate(ConnectionFields):
    preset: str
    model: str = Field(min_length=1)


class ActiveChoice(BaseModel):
    id: str | None


class TestRequest(ConnectionFields):
    id: str | None = None


def llm_router(connections: Callable[[], LLMConnections], rebuild: Callable[[], Awaitable[None]]) -> APIRouter:
    """`rebuild` makes the app pick up the active connection again after any change."""
    router = APIRouter(prefix="/api/llm")

    @router.get("/providers")
    def providers() -> list[dict[str, object]]:
        return connections().providers()

    @router.get("/connections")
    def listing() -> dict[str, Any]:
        return connections().listing()

    @router.post("/connections", status_code=201)
    async def create(body: ConnectionCreate) -> dict[str, Any]:
        return connections().create(body.model_dump(exclude_unset=True))

    @router.patch("/connections/{conn_id}")
    async def update(conn_id: str, body: ConnectionFields) -> dict[str, Any]:
        saved = connections().update(conn_id, body.model_dump(exclude_unset=True))
        await rebuild()
        return saved

    @router.delete("/connections/{conn_id}", status_code=204)
    async def delete(conn_id: str) -> Response:
        connections().delete(conn_id)
        await rebuild()
        return Response(status_code=204)

    @router.put("/active")
    async def set_active(body: ActiveChoice) -> dict[str, str | None]:
        active = connections().set_active(body.id)
        await rebuild()
        return {"active": active}

    @router.post("/test")
    async def test(body: TestRequest) -> dict[str, Any]:
        fields = body.model_dump(exclude_unset=True)
        return await connections().test(fields.pop("id", None), fields)

    return router
