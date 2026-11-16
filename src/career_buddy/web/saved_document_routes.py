"""HTTP routes for saved documents: save once as html, list, read the content, and download in any format later."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from career_buddy.application.ports import RendererUnavailable
from career_buddy.application.saved_documents import SavedDocuments, SavedMeta
from career_buddy.web.requests import SaveRequest

LISTED = ("id", "label", "template", "filename", "created_at", "ats_issues")


def saved_document_router(saved: Callable[[], SavedDocuments]) -> APIRouter:
    router = APIRouter(prefix="/api/saved-documents")

    def listed(meta: SavedMeta) -> dict[str, object]:
        record = asdict(meta)
        return {key: record[key] for key in LISTED}

    @router.get("")
    def list_saved() -> list[dict[str, object]]:
        return [listed(meta) for meta in saved().list()]

    @router.post("", status_code=201)
    async def save(body: SaveRequest) -> dict[str, object]:
        try:
            return listed(await saved().save(body.template, body.style, body.options, body.label))
        except KeyError as error:
            raise HTTPException(404, f"Unknown template: {error.args[0]}") from error

    @router.get("/{doc_id}/content")
    def content(doc_id: str) -> dict[str, object]:
        _, html, css, overrides = saved().content(doc_id)
        return {"html": html, "css": css, "overrides": overrides}

    @router.get("/{doc_id}/file")
    async def download(doc_id: str, format: Literal["docx", "pdf", "txt"] | None = None) -> Response:
        try:
            out = await saved().download(doc_id, format)
        except RendererUnavailable as error:
            raise HTTPException(503, str(error)) from error
        headers = {"Content-Disposition": f'attachment; filename="{out.filename}"'}
        if out.issues:  # a warning, not a block: the file still downloads
            headers["X-ATS-Issues"] = ",".join(issue.code for issue in out.issues)
        return Response(out.data, media_type=out.media_type, headers=headers)

    @router.delete("/{doc_id}", status_code=204)
    def remove(doc_id: str) -> Response:
        saved().delete(doc_id)
        return Response(status_code=204)

    return router
