"""HTTP route that writes the text of a document: the written document with its slot ids, never stored."""

from __future__ import annotations

from collections.abc import Callable
from fastapi import APIRouter, HTTPException

from career_buddy.application.generation import DocumentGeneration
from career_buddy.domain.document import Style
from career_buddy.web.requests import GenerateRequest


def document_router(generation: Callable[[], DocumentGeneration]) -> APIRouter:
    router = APIRouter(prefix="/api/documents")

    @router.post("/generate")
    async def generate(body: GenerateRequest) -> dict[str, object]:
        try:
            return (await generation().generate(body.template, body.options, body.instructions, body.pinned, body.resume_pages, body.template_instructions, Style(body.font, body.paper))).json()
        except KeyError as error:
            raise HTTPException(404, f"Unknown template: {error.args[0]}") from error

    return router
