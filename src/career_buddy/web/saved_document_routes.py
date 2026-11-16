"""HTTP routes for saved documents: render once, keep the file in the object store, list and download it later."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from career_buddy.application.ports import RendererUnavailable
from career_buddy.application.saved_documents import SavedDocuments, SavedMeta
from career_buddy.web.requests import SaveRequest

LISTED = ("id", "label", "template", "format", "filename", "created_at", "ats_issues")


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
            return listed(await saved().save(body.template, body.format, body.style, body.options, body.label))
        except KeyError as error:
            kind = "template" if error.args[0] == body.template else "format"
            raise HTTPException(404, f"Unknown {kind}: {error.args[0]}") from error
        except RendererUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/{doc_id}/file")
    def download(doc_id: str) -> Response:
        meta, data = saved().get_file(doc_id)
        return Response(data, media_type=meta.media_type, headers={"Content-Disposition": f'attachment; filename="{meta.filename}"'})

    @router.delete("/{doc_id}", status_code=204)
    def remove(doc_id: str) -> Response:
        saved().delete(doc_id)
        return Response(status_code=204)

    return router
