"""HTTP adapter. Thin: parses requests, calls the application services, returns results."""

from __future__ import annotations

import io
import mimetypes
import os
import zipfile
from collections.abc import AsyncIterator, Awaitable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from dataclasses import asdict
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from career_graph.application.documents import TailorOptions
from career_graph.application.ports import (
    DocumentRenderer,
    FactNotFound,
    LLMUnavailable,
    MissingInputs,
    RendererUnavailable,
    UnreadableDocument,
    UnsupportedFileType,
)
from career_graph.application.services import fact_json
from career_graph.composition import App, build_app
from career_graph.domain.document import Style
from career_graph.domain.model import FactKind, InvalidFact
from career_graph.domain.templates import TEMPLATES

STATIC = Path(__file__).parent / "static"
mimetypes.add_type("text/javascript", ".js")  # Windows can map .js to text/plain through the registry
mimetypes.add_type("text/css", ".css")
MAX_UPLOAD = 10 * 1024 * 1024


class TextImport(BaseModel):
    text: str
    source: str = "resume-text"


class JobText(BaseModel):
    job_text: str


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


class OrderPatch(BaseModel):
    order: int = Field(ge=0)


class DismissRequest(BaseModel):
    a_id: str
    b_id: str


class TailorRequest(BaseModel):
    template: str
    job_text: str = ""
    selection: list[str] | None = None  # bullet fact ids to keep, in place of the template's top-k
    overrides: dict[str, str] = {}  # bullet fact id -> the user's own wording
    inputs: dict[str, str] = {}  # template inputs: company, role, interviewer, ...

    @property
    def options(self) -> TailorOptions:
        selection = None if self.selection is None else frozenset(self.selection)
        return TailorOptions(self.job_text, selection, self.overrides, self.inputs)


class SuggestRequest(TailorRequest):
    job_text: str = Field(min_length=1)


class PreviewRequest(TailorRequest):
    format: str = "docx"  # the format whose ATS check the preview reports


class DocumentRequest(PreviewRequest):
    format: str
    font: Literal["sans", "serif"] = "sans"
    paper: Literal["letter", "a4"] = "letter"

    @property
    def style(self) -> Style:
        return Style(self.font, self.paper)


def create_app(
    data_dir: Path | None = None,
    llm_client: httpx.AsyncClient | None = None,
    renderers: Sequence[DocumentRenderer] = (),
) -> FastAPI:
    data_dir = data_dir or Path(os.environ.get("CAREER_GRAPH_DATA", "data"))
    state: dict[str, App] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["app"] = await build_app(data_dir, llm_client, renderers)
        yield

    api = FastAPI(title="career-graph", lifespan=lifespan)

    def app() -> App:
        return state["app"]

    @api.exception_handler(FactNotFound)
    def not_found(_: Request, error: FactNotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Unknown fact: {error}"}, status_code=404)

    @api.exception_handler(InvalidFact)
    def invalid(_: Request, error: InvalidFact) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=422)

    @api.exception_handler(LLMUnavailable)
    def llm_unavailable(_: Request, error: LLMUnavailable) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=503)

    @api.exception_handler(MissingInputs)
    def missing_inputs(_: Request, error: MissingInputs) -> JSONResponse:
        return JSONResponse({"detail": f"Missing required input: {error}"}, status_code=422)

    @api.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @api.post("/api/import/linkedin")
    async def import_linkedin(file: UploadFile) -> dict[str, int]:
        data = await file.read()
        if file.filename and file.filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                files = {n: archive.read(n) for n in archive.namelist() if n.lower().endswith(".csv")}
        else:
            files = {file.filename or "Profile.csv": data}
        if not files:
            raise HTTPException(400, "No CSV files found in upload")
        return {"facts": await app().imports.import_structured("linkedin", files, "linkedin-export")}

    @api.post("/api/import/text")
    async def import_text(body: TextImport) -> dict[str, int]:
        if not body.text.strip():
            raise HTTPException(400, "Text is empty")
        return {"facts": await app().imports.import_text(body.text, body.source)}

    @api.post("/api/import/file")
    async def import_file(file: UploadFile) -> dict[str, int]:
        # shortcut: the framework spools the whole body before this runs; fine on localhost, cap it at the proxy if exposed.
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File is over 10 MB")
        name = PurePosixPath((file.filename or "").replace("\\", "/")).name
        try:
            return {"facts": await app().imports.import_file(PurePosixPath(name).suffix.lower().lstrip("."), data, name)}
        except UnsupportedFileType as error:
            raise HTTPException(415, "Unsupported file type: use PDF, DOCX, TXT or MD") from error
        except UnreadableDocument as error:
            raise HTTPException(422, str(error)) from error

    @api.get("/api/facts")
    async def facts(kind: str | None = None) -> list[dict[str, object]]:
        return await app().queries.facts(kind)

    @api.patch("/api/facts/{fact_id}")
    async def revise_fact(fact_id: str, body: FactPatch) -> dict[str, object]:
        return fact_json(await app().edits.revise(fact_id, body.title, body.attributes))

    @api.patch("/api/facts/{fact_id}/order")
    async def order_fact(fact_id: str, body: OrderPatch) -> dict[str, object]:
        return fact_json(await app().edits.set_order(fact_id, body.order))

    @api.post("/api/facts", status_code=201)
    async def add_fact(body: FactCreate) -> dict[str, str]:
        return {"id": await app().edits.add_fact(body.kind, body.title, body.parent_id, body.attributes)}

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
                 "formats": app().documents.formats, "required": list(t.required), "optional": list(t.optional)}
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

    @api.post("/api/cover-letter", response_class=Response)
    async def cover_letter(body: JobText) -> Response:
        return Response(await app().queries.cover_letter(body.job_text), media_type="text/plain")

    @api.post("/api/fit")
    async def fit(body: JobText) -> dict[str, object]:
        return await app().queries.fit(body.job_text)

    api.mount("/static", StaticFiles(directory=STATIC), name="static")  # last: the routes above win
    return api
