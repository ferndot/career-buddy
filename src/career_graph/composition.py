"""Wires adapters to ports. The only place that knows which concrete adapter is used."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from career_graph.adapters.graph.memory_graph import MemoryFactGraph
from career_graph.adapters.inference.heuristic import HeuristicExtractor
from career_graph.adapters.inference.openai_compatible import OpenAICompatibleExtractor
from career_graph.adapters.inference.openai_rewriter import OpenAICompatibleRewriter
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
from career_graph.application.ports import DocumentRenderer, ObjectStore
from career_graph.application.projector import Projector
from career_graph.application.services import CareerQueries, EditService, ImportService


@dataclass
class App:
    imports: ImportService
    edits: EditService
    queries: CareerQueries
    documents: DocumentService


def object_store(data_dir: Path) -> ObjectStore:
    kind = os.environ.get("CAREER_GRAPH_STORAGE", "local")
    if kind == "local":
        return LocalObjectStore(data_dir / "objects")
    if kind == "s3":
        env = os.environ
        return S3ObjectStore(env["CAREER_GRAPH_S3_ENDPOINT"], env["CAREER_GRAPH_S3_BUCKET"], env["CAREER_GRAPH_S3_ACCESS_KEY"],
                             env["CAREER_GRAPH_S3_SECRET_KEY"], env.get("CAREER_GRAPH_S3_REGION", "us-east-1"))
    raise ValueError(f"CAREER_GRAPH_STORAGE must be 'local' or 's3', not {kind!r}")


async def build_app(
    data_dir: Path, llm_client: httpx.AsyncClient | None = None, extra_renderers: Sequence[DocumentRenderer] = ()
) -> App:
    log = JsonlEventLog(data_dir / "events.jsonl")
    projector = Projector(MemoryFactGraph())

    # Inference adapter: a model if one is configured, otherwise the offline heuristic.
    base_url = os.environ.get("CAREER_GRAPH_LLM_BASE_URL")
    extractor = (
        OpenAICompatibleExtractor(base_url, os.environ.get("CAREER_GRAPH_LLM_MODEL", "default"),
                                  os.environ.get("CAREER_GRAPH_LLM_API_KEY", "none"))
        if base_url
        else HeuristicExtractor()
    )

    # Rewording is optional: it needs a model. `llm_client` lets tests supply one over a MockTransport.
    model = os.environ.get("CAREER_GRAPH_LLM_MODEL", "default")
    if llm_client is None and base_url:
        key = os.environ.get("CAREER_GRAPH_LLM_API_KEY", "none")
        llm_client = httpx.AsyncClient(base_url=base_url, headers={"Authorization": f"Bearer {key}"}, timeout=120)
    rewriter = OpenAICompatibleRewriter(llm_client, model) if llm_client else None

    readers = {
        "markdown": PlainTextReader(),
        "txt": PlainTextReader(),
        "html": HtmlTextReader(),
        "docx": DocxTextReader(),
        "pdf": PdfTextReader(),
    }
    file_readers = {ext: readers[ext] for ext in ("pdf", "docx", "txt")} | {"md": readers["markdown"]}
    imports = ImportService(log, projector, {"linkedin": LinkedInExportParser()}, extractor, file_readers, object_store(data_dir))
    # Projection rebuild: the log is the truth, the graph is derived from it.
    for event in log.replay():
        await projector.project(event)

    renderers = {
        r.format: r for r in (MarkdownRenderer(), HtmlRenderer(), TextRenderer(), DocxRenderer(), PdfRenderer(), *extra_renderers)
    }
    return App(imports, EditService(log, projector), CareerQueries(projector),
               DocumentService(projector, renderers, readers, rewriter))
