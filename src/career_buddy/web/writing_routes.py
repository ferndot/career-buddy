"""HTTP routes for the general writing rules a person can replace per document kind, and the strictness level (Settings > Writing)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field, StringConstraints

from career_buddy.adapters.storage.writing_rules_store import WritingRulesStore
from career_buddy.domain.strictness import DEFAULT, Strictness
from career_buddy.domain.writing_rules import DEFAULT_RULES

Kind = Literal["resume", "letter"]
Rule = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class StrictnessBody(BaseModel):
    strictness: Strictness


class RulesBody(BaseModel):
    rules: list[Rule] = Field(max_length=20)


def writing_router(store: Callable[[], WritingRulesStore]) -> APIRouter:
    router = APIRouter(prefix="/api/writing")

    def view(kind: Kind) -> dict[str, object]:
        return {"rules": list(store().rules(kind)), "default": list(DEFAULT_RULES[kind]), "custom": bool(store().custom(kind))}

    @router.get("/rules")
    def listing() -> dict[str, dict[str, object]]:
        return {k: view(k) for k in DEFAULT_RULES}

    @router.put("/rules/{kind}")
    def save(kind: Kind, body: RulesBody) -> dict[str, object]:
        store().save(kind, body.rules)  # an empty list is the default again
        return view(kind)

    @router.delete("/rules/{kind}", status_code=204)
    def reset(kind: Kind) -> Response:
        store().save(kind, [])
        return Response(status_code=204)

    @router.get("/strictness")
    def level() -> dict[str, str]:
        return {"strictness": store().strictness(), "default": DEFAULT}

    @router.put("/strictness")
    def set_level(body: StrictnessBody) -> dict[str, str]:
        store().set_strictness(body.strictness)
        return level()

    return router
