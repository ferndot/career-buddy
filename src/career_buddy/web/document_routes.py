"""HTTP route that writes the text of a document: a draft keyed by slot id, never stored."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from career_buddy.application.generation import DocumentGeneration
from career_buddy.web.requests import GenerateRequest


def document_router(generation: Callable[[], DocumentGeneration]) -> APIRouter:
    router = APIRouter(prefix="/api/documents")

    @router.post("/generate")
    async def generate(body: GenerateRequest) -> dict[str, object]:
        try:
            return asdict(await generation().generate(body.template, body.options, body.instructions, body.pinned, body.resume_pages, body.template_instructions))
        except KeyError as error:
            raise HTTPException(404, f"Unknown template: {error.args[0]}") from error

    return router
