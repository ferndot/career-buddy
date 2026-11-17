"""HTTP adapter. Thin: parses requests, calls the application services, returns results."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Awaitable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from dataclasses import asdict
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from career_buddy.adapters.inference.connections import InvalidConnection, ReadOnlyConnection, UnknownConnection
from career_buddy.adapters.jobs.source_log import SourceLog, SourceLogHandler
from career_buddy.adapters.sources.job_link import JobLinkError, JobLinkFetcher
from career_buddy.application.ports import (
    DocumentRenderer,
    FactNotFound,
    LLMUnavailable,
    MissingInputs,
    NoOriginal,
    RendererUnavailable,
    SourceBusy,
    SourceNotFound,
    UnreadableDocument,
    UnsupportedFileType,
)
from career_buddy.application.generation import UngroundedDraft
from career_buddy.application.saved_documents import NoSource, SavedDocumentNotFound
from career_buddy.application.services import fact_json
from career_buddy.composition import App, build_app, new_jobs
from career_buddy.domain.model import FactKind, InvalidFact
from career_buddy.domain.templates import TEMPLATES
from career_buddy.web.document_routes import document_router
from career_buddy.web.llm_routes import llm_router
from career_buddy.web.requests import DocumentRequest, PreviewRequest, SuggestRequest, TailorRequest
from career_buddy.web.saved_document_routes import saved_document_router
from career_buddy.paths import default_data_dir
from career_buddy.web.source_log_routes import source_log_router
from career_buddy.web.ui import mount_ui

MAX_UPLOAD = 10 * 1024 * 1024


class TextImport(BaseModel):
    text: str
    source: str = "resume-text"


class JobText(BaseModel):
    job_text: str


class JobLink(BaseModel):
    url: str


class FactPatch(BaseModel):
    title: str | None = Field(None, min_length=1)
    attributes: dict[str, str] | None = None


class FactCreate(BaseModel):
    kind: FactKind
    title: str = Field(min_length=1)
    parent_id: str | None = None
    attributes: dict[str, str] = {}


class MergeRequest(BaseModel):
    alias_id: str
    canonical_id: str
    undo: bool = False


class LinkRequest(BaseModel):
    source_id: str
    target_id: str
    kind: str


class OrderPatch(BaseModel):
    order: int = Field(ge=0)


class DismissRequest(BaseModel):
    a_id: str
    b_id: str


def connection_error(error: Exception) -> str:
    if isinstance(error, UnknownConnection):
        return "That connection no longer exists."
    if isinstance(error, ReadOnlyConnection):
        return "This connection comes from environment variables. Change it there."
    return str(error)


def create_app(
    data_dir: Path | None = None,
    llm_transport: httpx.AsyncBaseTransport | None = None,
    renderers: Sequence[DocumentRenderer] = (),
    job_fetcher: JobLinkFetcher | None = None,
) -> FastAPI:
    data_dir = data_dir or Path(os.environ.get("CAREER_BUDDY_DATA") or default_data_dir())
    # uvicorn only configures its own loggers; without this the extraction logs never show. No-op if the host app set up logging.
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("career_buddy").setLevel(os.environ.get("CAREER_BUDDY_LOG_LEVEL", "INFO").upper())
    state: dict[str, App] = {}
    job_fetcher = job_fetcher or JobLinkFetcher()
    source_log = SourceLog()
    jobs = new_jobs(source_log.start)

    async def rebuild() -> None:
        state["app"] = await build_app(data_dir, jobs, llm_transport, renderers)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        handler = SourceLogHandler(source_log)  # off again at shutdown, so apps made one after another do not collect each other's lines
        logging.getLogger("career_buddy").addHandler(handler)
        try:
            await rebuild()
            yield
        finally:
            logging.getLogger("career_buddy").removeHandler(handler)

    api = FastAPI(title="career-buddy", lifespan=lifespan)
    # Only this computer may talk to the API: a web page on another site cannot reach it through DNS rebinding.
    # shortcut: "[::1]" is not matched (the middleware cannot parse it), so use 127.0.0.1 or localhost.
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", *filter(None, os.environ.get("CAREER_BUDDY_ALLOWED_HOSTS", "").split(","))])

    # The dev server of the separate frontend is a different origin. Only the listed origins may call the API.
    origins = os.environ.get("CAREER_BUDDY_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    api.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
                       allow_methods=["*"], allow_headers=["*"])

    def app() -> App:
        return state["app"]

    @api.exception_handler(FactNotFound)
    def not_found(_: Request, error: FactNotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Unknown fact: {error}"}, status_code=404)

    for error_type, status, message in ((SavedDocumentNotFound, 404, "Unknown saved document"), (NoSource, 409, "This document was saved before it kept what it was built from, so it cannot be written again"), (SourceNotFound, 404, "Unknown source"), (SourceBusy, 409, "This source is still being processed"),
                                        (NoOriginal, 422, "This source has no original file to read again")):
        api.exception_handler(error_type)(lambda _, error, status=status, message=message: JSONResponse({"detail": message}, status_code=status))

    @api.exception_handler(InvalidFact)
    def invalid(_: Request, error: InvalidFact) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=422)

    @api.exception_handler(LLMUnavailable)
    def llm_unavailable(_: Request, error: LLMUnavailable) -> JSONResponse:
        return JSONResponse({"detail": str(error), "code": "llm_unavailable"}, status_code=503)  # a stable code the pages can act on

    @api.exception_handler(UngroundedDraft)
    def ungrounded(_: Request, error: UngroundedDraft) -> JSONResponse:  # 502: the model answered, but not with text the facts support
        return JSONResponse({"detail": str(error), "code": "ungrounded",
                             "rejected": [{"slot": r.slot, "reasons": list(r.reasons)} for r in error.rejected]}, status_code=502)

    for error_type, status in ((InvalidConnection, 422), (UnknownConnection, 404), (ReadOnlyConnection, 409)):
        api.exception_handler(error_type)(lambda _, error, status=status: JSONResponse({"detail": connection_error(error)}, status_code=status))

    @api.exception_handler(MissingInputs)
    def missing_inputs(_: Request, error: MissingInputs) -> JSONResponse:
        return JSONResponse({"detail": f"Missing required input: {error}"}, status_code=422)

    api.include_router(llm_router(lambda: app().llm, rebuild))
    api.include_router(saved_document_router(lambda: app().saved))
    api.include_router(document_router(lambda: app().generation))
    api.include_router(source_log_router(source_log, lambda: app().queries.sources()))

    async def started(source: str, facts: int | None) -> Response | dict[str, int]:
        """Done: the fact count. Queued behind a model call: 202 and the source record, to poll in GET /api/sources."""
        if facts is None:
            return JSONResponse(await app().queries.source(source), status_code=202)
        return {"facts": facts}

    @api.post("/api/import/text", response_model=None)
    async def import_text(body: TextImport) -> Response | dict[str, int]:
        if not body.text.strip():
            raise HTTPException(400, "Text is empty")
        return await started(body.source, await app().imports.import_text(body.text, body.source))

    @api.post("/api/import/file", response_model=None)
    async def import_file(file: UploadFile) -> Response | dict[str, int]:
        # shortcut: the framework spools the whole body before this runs; fine on localhost, cap it at the proxy if exposed.
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File is over 10 MB")
        name = PurePosixPath((file.filename or "").replace("\\", "/")).name
        try:
            return await started(name, await app().imports.import_file(PurePosixPath(name).suffix.lower().lstrip("."), data, name))
        except UnsupportedFileType as error:
            raise HTTPException(415, "Unsupported file type: use PDF, DOCX, TXT or MD") from error
        except UnreadableDocument as error:
            raise HTTPException(422, str(error)) from error

    @api.post("/api/job/fetch")
    async def fetch_job(body: JobLink) -> dict[str, str]:
        try:
            return {"text": await job_fetcher.fetch(body.url.strip())}
        except JobLinkError as error:
            raise HTTPException(error.status, str(error)) from error

    @api.get("/api/sources")
    async def sources() -> list[dict[str, object]]:
        return await app().queries.sources()

    @api.post("/api/sources/{source}/reindex", status_code=202)
    async def reindex_source(source: str) -> dict[str, object]:
        await app().imports.reindex(source)
        return await app().queries.source(source)

    @api.delete("/api/sources/{source}", status_code=204)
    async def remove_source(source: str) -> Response:
        await app().edits.remove_source(source)
        source_log.drop(source)
        return Response(status_code=204)

    @api.get("/api/graph")
    async def graph() -> dict[str, list[dict[str, object]]]:
        return await app().queries.graph()

    @api.get("/api/facts")
    async def facts(kind: str | None = None) -> list[dict[str, object]]:
        return await app().queries.facts(kind)

    @api.patch("/api/facts/{fact_id}")
    async def revise_fact(fact_id: str, body: FactPatch) -> dict[str, object]:
        return fact_json(await app().edits.revise(fact_id, body.title, body.attributes))

    @api.delete("/api/facts/{fact_id}", status_code=204)
    async def delete_fact(fact_id: str) -> Response:
        await app().edits.delete(fact_id)
        return Response(status_code=204)

    @api.patch("/api/facts/{fact_id}/order")
    async def order_fact(fact_id: str, body: OrderPatch) -> dict[str, object]:
        return fact_json(await app().edits.set_order(fact_id, body.order))

    @api.post("/api/facts", status_code=201)
    async def add_fact(body: FactCreate) -> dict[str, str]:
        return {"id": await app().edits.add_fact(body.kind, body.title, body.parent_id, body.attributes)}

    @api.post("/api/links", status_code=201)
    async def add_link(body: LinkRequest) -> dict[str, str]:
        await app().edits.add_link(body.source_id, body.target_id, body.kind)
        return {}

    @api.delete("/api/links", status_code=204)
    async def remove_link(source_id: str, target_id: str, kind: str) -> Response:
        await app().edits.remove_link(source_id, target_id, kind)
        return Response(status_code=204)

    @api.get("/api/duplicates")
    async def duplicates() -> list[dict[str, object]]:
        return await app().queries.duplicates()

    @api.post("/api/duplicates/dismiss")
    async def dismiss_duplicate(body: DismissRequest) -> DismissRequest:
        await app().edits.dismiss(body.a_id, body.b_id)
        return body

    @api.post("/api/merges")
    async def merge(body: MergeRequest) -> MergeRequest:
        await app().edits.merge(body.alias_id, body.canonical_id, body.undo)
        return body

    @api.get("/api/templates")
    async def templates() -> list[dict[str, Any]]:
        return [{"id": t.id, "kind": t.kind, "label": t.label,
                 "formats": app().documents.formats, "required": list(t.required), "optional": list(t.optional),
                 "sections": [label for _, label in t.sections], "layout": asdict(t.layout), "instructions": t.instructions,
                 "styles": [asdict(s) for s in t.styles]}
                for t in TEMPLATES]

    @api.get("/api/profile")
    async def profile() -> dict[str, Any]:
        return asdict(await app().queries.profile())

    async def documents(body: TailorRequest, call: Awaitable[Any]) -> Any:
        try:
            return await call
        except KeyError as error:
            kind = "template" if error.args[0] == body.template else "format"
            raise HTTPException(404, f"Unknown {kind}: {error.args[0]}") from error
        except RendererUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @api.post("/api/documents/render")
    async def render_document(body: DocumentRequest) -> Response:
        out = await documents(body, app().documents.render(body.template, body.format, body.style, body.options))
        headers = {"Content-Disposition": f'attachment; filename="{out.filename}"'}
        if out.issues:  # a warning, not a block: the file still downloads
            headers["X-ATS-Issues"] = ",".join(issue.code for issue in out.issues)
        return Response(out.data, media_type=out.media_type, headers=headers)

    @api.post("/api/documents/check")
    async def check_document(body: DocumentRequest) -> dict[str, object]:
        issues = await documents(body, app().documents.check(body.template, body.format, body.style, body.options))
        return {"passes": not issues, "issues": [{"code": i.code, "message": i.message} for i in issues]}

    @api.post("/api/documents/preview")
    async def preview_document(body: PreviewRequest) -> dict[str, Any]:
        out = await documents(body, app().documents.preview(body.template, body.options, body.format))
        issues = [{"code": i.code, "message": i.message} for i in out.issues]
        return {"lines": out.document.lines(), "document": asdict(out.document), "tailoring": asdict(out.report),
                "markers": [{**asdict(change), "weak": change.weak} for change in out.markers],
                "ats": {"format": out.format, "passes": not issues, "issues": issues}}

    @api.post("/api/documents/suggest")
    async def suggest_rewordings(body: SuggestRequest) -> dict[str, Any]:
        return asdict(await documents(body, app().documents.suggest(body.template, body.options)))

    @api.get("/api/resume/{fmt}")
    async def resume(fmt: str) -> Response:
        if fmt not in ("markdown", "html"):
            raise HTTPException(404, "Unknown format")
        body = DocumentRequest(template="resume-classic", format=fmt)
        out = await documents(body, app().documents.render(body.template, body.format))
        return Response(out.data, media_type=out.media_type)

    @api.post("/api/fit")
    async def fit(body: JobText) -> dict[str, object]:
        return await app().queries.fit(body.job_text)

    mount_ui(api)  # last: the mount at "/" must come after every API route
    return api
