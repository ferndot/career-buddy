"""Wires adapters to ports. The only place that knows which concrete adapter is used."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from career_graph.adapters.consolidation.redstring_candidates import skill_candidates
from career_graph.adapters.graph.redstring_graph import RedstringFactGraph
from career_graph.adapters.inference.heuristic import HeuristicExtractor
from career_graph.adapters.inference.connections import LLMConnections
from career_graph.adapters.jobs.memory_jobs import InMemoryJobStore
from career_graph.adapters.outputs.render_docx import DocxRenderer
from career_graph.adapters.outputs.render_html import HtmlRenderer
from career_graph.adapters.outputs.render_markdown import MarkdownRenderer
from career_graph.adapters.outputs.render_pdf import PdfRenderer
from career_graph.adapters.outputs.render_text import TextRenderer
from career_graph.adapters.readers.docx_text import DocxTextReader
from career_graph.adapters.readers.markup_text import HtmlTextReader, PlainTextReader
from career_graph.adapters.readers.pdf_text import PdfTextReader
from career_graph.adapters.sources.linkedin_export import LinkedInExportParser
from career_graph.adapters.storage.jsonl_event_log import JsonlEventLog
from career_graph.adapters.storage.local_object_store import LocalObjectStore
from career_graph.adapters.storage.s3_object_store import S3ObjectStore
from career_graph.application.documents import DocumentService
from career_graph.application.jobs import SourceJobs
from career_graph.application.ports import DocumentRenderer, ObjectStore
from career_graph.application.projector import Projector
from career_graph.application.saved_documents import SavedDocuments
from career_graph.application.services import CareerQueries, EditService, ImportService


@dataclass
class App:
    imports: ImportService
    edits: EditService
    queries: CareerQueries
    documents: DocumentService
    saved: SavedDocuments
    llm: LLMConnections


def object_store(data_dir: Path) -> ObjectStore:
    kind = os.environ.get("CAREER_GRAPH_STORAGE", "local")
    if kind == "local":
        return LocalObjectStore(data_dir / "objects")
    if kind == "s3":
        env = os.environ
        return S3ObjectStore(env["CAREER_GRAPH_S3_ENDPOINT"], env["CAREER_GRAPH_S3_BUCKET"], env["CAREER_GRAPH_S3_ACCESS_KEY"],
                             env["CAREER_GRAPH_S3_SECRET_KEY"], env.get("CAREER_GRAPH_S3_REGION", "us-east-1"))
    raise ValueError(f"CAREER_GRAPH_STORAGE must be 'local' or 's3', not {kind!r}")


def new_jobs() -> SourceJobs:
    """Processing state outlives a rebuild of the app (a changed LLM connection), so the caller makes it once."""
    return SourceJobs(InMemoryJobStore())


async def build_app(
    data_dir: Path,
    jobs: SourceJobs,
    llm_transport: httpx.AsyncBaseTransport | None = None,
    extra_renderers: Sequence[DocumentRenderer] = (),
) -> App:
    log = JsonlEventLog(data_dir / "events.jsonl")
    projector = Projector(RedstringFactGraph())

    # Inference adapter: the active LLM connection if there is one, otherwise the offline heuristic.
    llm = LLMConnections(data_dir, llm_transport)
    model = llm.inference()
    extractor, rewriter = model or (HeuristicExtractor(), None)

    readers = {
        "markdown": PlainTextReader(),
        "txt": PlainTextReader(),
        "html": HtmlTextReader(),
        "docx": DocxTextReader(),
        "pdf": PdfTextReader(),
    }
    file_readers = {ext: readers[ext] for ext in ("pdf", "docx", "txt")} | {"md": readers["markdown"]}
    store = object_store(data_dir)
    imports = ImportService(log, projector, {"linkedin": LinkedInExportParser()}, extractor, file_readers, store,
                            jobs, background=model is not None)  # a model call is slow, the heuristic is not
    # Projection rebuild: the log is the truth, the graph is derived from it.
    for event in log.replay():
        await projector.project(event)

    renderers = {
        r.format: r for r in (MarkdownRenderer(), HtmlRenderer(), TextRenderer(), DocxRenderer(), PdfRenderer(), *extra_renderers)
    }
    documents = DocumentService(projector, renderers, readers, rewriter, merged=projector)
    return App(imports, EditService(log, projector, jobs, extractor), CareerQueries(projector, jobs, skill_matcher=skill_candidates), documents,
               SavedDocuments(store, documents), llm)
