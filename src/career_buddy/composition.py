"""Wires adapters to ports. The only place that knows which concrete adapter is used."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from career_buddy.adapters.consolidation.redstring_candidates import skill_candidates
from career_buddy.adapters.graph.redstring_graph import RedstringFactGraph
from career_buddy.adapters.inference.heuristic import HeuristicExtractor
from career_buddy.adapters.inference.connections import LLMConnections
from career_buddy.adapters.jobs.memory_jobs import InMemoryJobStore
from career_buddy.adapters.outputs.render_docx import DocxRenderer
from career_buddy.adapters.outputs.render_html import HtmlRenderer, document_css, stored_html
from career_buddy.adapters.outputs.render_markdown import MarkdownRenderer
from career_buddy.adapters.outputs.render_pdf import PdfRenderer
from career_buddy.adapters.outputs.render_text import TextRenderer
from career_buddy.adapters.readers.docx_text import DocxTextReader
from career_buddy.adapters.readers.html_document import read_document, read_slots
from career_buddy.adapters.readers.markup_text import HtmlTextReader, PlainTextReader
from career_buddy.adapters.readers.pdf_text import PdfTextReader
from career_buddy.adapters.storage.jsonl_event_log import JsonlEventLog
from career_buddy.adapters.storage.local_object_store import LocalObjectStore
from career_buddy.adapters.storage.s3_object_store import S3ObjectStore
from career_buddy.adapters.storage.writing_rules_store import WritingRulesStore
from career_buddy.application.chat_tools import ChatTools
from career_buddy.application.documents import DocumentService
from career_buddy.application.generation import DocumentGeneration
from career_buddy.application.jobs import SourceJobs
from career_buddy.application.ports import DocumentRenderer, ObjectStore, PageCounter
from career_buddy.application.projector import Projector
from career_buddy.application.saved_documents import HtmlCodec, SavedDocuments
from career_buddy.application.services import CareerQueries, EditService, ImportService


@dataclass
class App:
    imports: ImportService
    edits: EditService
    queries: CareerQueries
    documents: DocumentService
    saved: SavedDocuments
    generation: DocumentGeneration
    llm: LLMConnections
    rules: WritingRulesStore
    chat_tools: ChatTools


def object_store(data_dir: Path) -> ObjectStore:
    kind = os.environ.get("CAREER_BUDDY_STORAGE", "local")
    if kind == "local":
        return LocalObjectStore(data_dir / "objects")
    if kind == "s3":
        env = os.environ
        return S3ObjectStore(env["CAREER_BUDDY_S3_ENDPOINT"], env["CAREER_BUDDY_S3_BUCKET"], env["CAREER_BUDDY_S3_ACCESS_KEY"],
                             env["CAREER_BUDDY_S3_SECRET_KEY"], env.get("CAREER_BUDDY_S3_REGION", "us-east-1"))
    raise ValueError(f"CAREER_BUDDY_STORAGE must be 'local' or 's3', not {kind!r}")


def new_jobs(on_start: Callable[[str], None] = lambda source: None) -> SourceJobs:
    """Processing state outlives a rebuild of the app (a changed LLM connection), so the caller makes it once."""
    return SourceJobs(InMemoryJobStore(), on_start)


async def build_app(
    data_dir: Path,
    jobs: SourceJobs,
    llm_transport: httpx.AsyncBaseTransport | None = None,
    extra_renderers: Sequence[DocumentRenderer] = (),
    page_counter: PageCounter | None = None,
    source_removed: Callable[[str], None] = lambda _: None,  # told when the chat removes a source, so its import log goes too
) -> App:
    log = JsonlEventLog(data_dir / "events.jsonl")
    projector = Projector(RedstringFactGraph())

    # Inference adapter: the active LLM connection if there is one, otherwise the offline heuristic.
    llm = LLMConnections(data_dir, llm_transport)
    model = llm.inference()
    extractor = model.extractor if model else HeuristicExtractor()

    def current(part: str) -> Callable[[], Any]:
        """The active connection's rewriter, writer, reviewer or chat, read at each request and never kept: Settings can change it."""
        return lambda: getattr(m, part) if (m := llm.inference()) else None

    readers = {
        "markdown": PlainTextReader(),
        "txt": PlainTextReader(),
        "html": HtmlTextReader(),
        "docx": DocxTextReader(),
        "pdf": PdfTextReader(),
    }
    file_readers = {ext: readers[ext] for ext in ("pdf", "docx", "txt")} | {"md": readers["markdown"]}
    store = object_store(data_dir)
    imports = ImportService(log, projector, extractor, file_readers, store,
                            jobs, background=model is not None)  # a model call is slow, the heuristic is not
    # Projection rebuild: the log is the truth, the graph is derived from it.
    for event in log.replay():
        await projector.project(event)

    renderers = {
        r.format: r for r in (MarkdownRenderer(), HtmlRenderer(), TextRenderer(), DocxRenderer(), PdfRenderer(), *extra_renderers)
    }
    documents = DocumentService(projector, renderers, readers, current("rewriter"), merged=projector)
    rules = WritingRulesStore(data_dir)
    generation = DocumentGeneration(documents, current("writer"), rules.rules, page_counter, rules.strictness)
    edits = EditService(log, projector, jobs, extractor)
    queries = CareerQueries(projector, jobs, skill_matcher=skill_candidates, reviewer=current("reviewer"))
    return App(imports, edits, queries, documents,
               SavedDocuments(store, documents, HtmlCodec(stored_html, document_css, read_slots, read_document), generation), generation, llm, rules, ChatTools(queries, edits, source_removed))
