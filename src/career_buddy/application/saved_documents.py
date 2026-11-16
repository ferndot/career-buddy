"""Saved documents, kept in the object store under `documents/<id>/`.

A saved document is live. It keeps a layout of restricted HTML plus CSS (`document.html`, `document.css`), what the user
wrote (`overrides.json`, by slot id), what a writer generated (`generated.json`) and what it was built from (`source.json`:
the ticked facts and the settings). The text of every other slot is found when the document is read (domain/slots.py), so a
later edit to a fact shows in the next download. The document is converted to the requested format at download time.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime

from career_buddy.application.documents import DocumentService, Rendered, TailorOptions
from career_buddy.application.generation import Draft, DocumentGeneration
from career_buddy.application.ports import ObjectNotFound, ObjectStore
from career_buddy.domain.document import Document, Style
from career_buddy.domain.markers import clean_document
from career_buddy.domain.slots import Slot, Written, layout_overrides, paragraph_indexes, resolve, with_paragraphs, written_for
from career_buddy.domain.templates import get_template

_ID = re.compile(r"[0-9a-f]{32}")
DEFAULT_FORMAT = "docx"


@dataclass(frozen=True)
class HtmlCodec:
    """How a document is kept: written to a layout in html and css, read back with the text of each slot."""

    write: Callable[[Document], str]
    css: Callable[[Style], str]
    slots: Callable[[str], list[Slot]]
    read: Callable[[str, dict[str, str], frozenset[str]], Document]


class SavedDocumentNotFound(Exception):
    """No saved document has this id, or the id is not a valid one."""


class NoSource(Exception):
    """The document was saved before it kept what it was built from, so it cannot be written again."""


@dataclass(frozen=True)
class SavedMeta:
    id: str
    label: str
    template: str
    filename: str  # without extension
    created_at: str  # ISO 8601, UTC
    ats_issues: list[str]  # codes of the failed ATS checks at save time
    font: str
    paper: str


@dataclass(frozen=True)
class SavedSource:
    """What a document was built from: which facts were ticked, and the job and directions. No text of its own."""

    template: str
    job_text: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    selection: list[str] | None = None  # bullet fact ids; None means the template's own choice
    skill_ids: list[str] | None = None
    education_ids: list[str] | None = None
    instructions: str = ""  # the user's directions for the writer
    resume_pages: int = 1  # how long a resume should be: 1, 2 or 3 pages

    @staticmethod
    def of(template: str, options: TailorOptions, instructions: str, resume_pages: int) -> SavedSource:
        def ids(chosen: frozenset[str] | None) -> list[str] | None:
            return None if chosen is None else sorted(chosen)

        return SavedSource(template, options.job_text, options.inputs, ids(options.selection), ids(options.skills), ids(options.education), instructions, resume_pages)

    def options(self, overrides: dict[str, str]) -> TailorOptions:
        def ids(chosen: list[str] | None) -> frozenset[str] | None:
            return None if chosen is None else frozenset(chosen)

        return TailorOptions(self.job_text, ids(self.selection), overrides, self.inputs, ids(self.skill_ids), ids(self.education_ids))


@dataclass(frozen=True)
class SavedContent:
    meta: SavedMeta
    html: str
    css: str
    overrides: dict[str, str]  # the user's own wording, by slot id
    generated: dict[str, Written]  # what a writer wrote, by slot id
    source: SavedSource | None  # None for a document saved before sources were kept


def _prefix(doc_id: str) -> str:
    if not _ID.fullmatch(doc_id):
        raise SavedDocumentNotFound(doc_id)
    return f"documents/{doc_id}/"


def _parse(raw: bytes) -> SavedMeta:
    return SavedMeta(**json.loads(raw))


class SavedDocuments:
    def __init__(self, store: ObjectStore, documents: DocumentService, html: HtmlCodec, generation: DocumentGeneration) -> None:
        self._store = store
        self._documents = documents
        self._html = html
        self._generation = generation

    async def _document(self, html: str, overrides: Mapping[str, str], generated: Mapping[str, Written]) -> Document:
        """The layout read with its slots resolved against the facts as they are now."""
        texts = resolve(self._html.slots(html), overrides, await self._documents.lookup(), generated)
        return clean_document(self._html.read(html, texts, frozenset(overrides)))[0]

    async def _layout(self, template: str, options: TailorOptions, texts: Mapping[str, str]) -> tuple[str, str]:
        """The layout html and the file stem. `texts` is every text kept for the document, the user's and the writer's: a summary
        or a letter's paragraphs among them need a slot to sit in. KeyError: unknown template."""
        summary = {"summary": texts["summary"]} if texts.get("summary") else {}
        doc, stem = await self._documents.compose(template, replace(options, overrides={**summary, **options.overrides}))
        if (paragraphs := paragraph_indexes(texts)) and get_template(template).kind == "letter":  # a letter written by the user or the model: its body is those paragraphs
            doc = with_paragraphs(doc, paragraphs[-1])
        return self._html.write(doc), stem

    def _put(self, doc_id: str, name: str, data: object, content_type: str = "application/json") -> None:
        self._store.put(f"{_prefix(doc_id)}{name}", data if isinstance(data, bytes) else json.dumps(data).encode(), content_type)

    async def save(self, template: str, style: Style, options: TailorOptions, label: str = "",
                   generated: Mapping[str, str] | None = None, instructions: str = "", resume_pages: int = 1) -> SavedMeta:
        """Keep the layout, what the user wrote (`options.overrides`) and what a writer generated, both by slot id or fact id,
        and what the document was built from. The facts' own text is not kept: it is found when the document is read."""
        generated = generated or {}
        html, stem = await self._layout(template, options, {**generated, **options.overrides})
        slots = self._html.slots(html)
        overrides = layout_overrides(options.overrides, (slot.id for slot in slots))
        made = written_for(slots, layout_overrides(generated, (slot.id for slot in slots)), await self._documents.lookup())
        issues = (await self._documents.export(await self._document(html, overrides, made), DEFAULT_FORMAT, style, stem)).issues
        doc_id = uuid.uuid4().hex
        meta = SavedMeta(doc_id, label.strip() or stem, template, stem, datetime.now(UTC).isoformat(),
                         [issue.code for issue in issues], style.font, style.paper)
        self._put(doc_id, "document.html", html.encode(), "text/html")
        self._put(doc_id, "document.css", self._html.css(style).encode(), "text/css")
        self._put(doc_id, "overrides.json", overrides)
        self._put(doc_id, "generated.json", {k: asdict(w) for k, w in made.items()})
        self._put(doc_id, "source.json", asdict(SavedSource.of(template, options, instructions.strip(), resume_pages)))
        self._put(doc_id, "meta.json", asdict(meta))  # last: a record means a complete save
        return meta

    def _meta(self, doc_id: str) -> SavedMeta:
        try:
            return _parse(self._store.get(f"{_prefix(doc_id)}meta.json"))
        except ObjectNotFound as error:
            raise SavedDocumentNotFound(doc_id) from error

    def list(self) -> list[SavedMeta]:
        keys = (k for k in self._store.list("documents/") if k.endswith("/meta.json"))
        return sorted((_parse(self._store.get(k)) for k in keys), key=lambda m: m.created_at, reverse=True)

    def _read(self, doc_id: str, name: str) -> bytes:
        try:
            return self._store.get(f"{_prefix(doc_id)}{name}")
        except ObjectNotFound as error:
            raise SavedDocumentNotFound(doc_id) from error

    def _json(self, doc_id: str, name: str) -> dict:
        try:
            return json.loads(self._store.get(f"{_prefix(doc_id)}{name}"))
        except ObjectNotFound:
            return {}  # a document saved before this file existed

    def content(self, doc_id: str) -> SavedContent:
        meta = self._meta(doc_id)
        source = self._json(doc_id, "source.json")
        return SavedContent(meta, self._read(doc_id, "document.html").decode(), self._read(doc_id, "document.css").decode(),
                            self._json(doc_id, "overrides.json"), {k: Written(**v) for k, v in self._json(doc_id, "generated.json").items()},
                            SavedSource(**source) if source else None)

    async def slots(self, doc_id: str) -> dict[str, str]:
        """The text of every slot as it reads now: override, generated text, the facts, then the placeholder."""
        c = self.content(doc_id)
        return resolve(self._html.slots(c.html), c.overrides, await self._documents.lookup(), c.generated)

    async def download(self, doc_id: str, fmt: str | None = None) -> Rendered:
        """The file: the layout with its slots resolved now, converted to `fmt` (default docx)."""
        c = self.content(doc_id)
        doc = await self._document(c.html, c.overrides, c.generated)
        return await self._documents.export(doc, fmt or DEFAULT_FORMAT, Style(c.meta.font, c.meta.paper), c.meta.filename)  # type: ignore[arg-type]

    async def regenerate(self, doc_id: str, instructions: str = "", resume_pages: int | None = None) -> Draft:
        """Write the text again from the facts as they are now. It replaces generated text only: a slot with an override is
        pinned, left to the writer untouched, and keeps the user's words. NoSource: saved before sources were kept.
        LLMUnavailable and UngroundedDraft as for DocumentGeneration."""
        c = self.content(doc_id)
        if c.source is None:
            raise NoSource(doc_id)
        source = replace(c.source, instructions=instructions.strip() or c.source.instructions, resume_pages=resume_pages or c.source.resume_pages)
        options = source.options(c.overrides)
        draft = await self._generation.generate(source.template, options, source.instructions, c.overrides, source.resume_pages)
        html, _ = await self._layout(source.template, options, {**draft.slots, **c.overrides})
        slots = self._html.slots(html)
        fresh = {k: v for k, v in layout_overrides(draft.slots, (slot.id for slot in slots)).items() if k not in c.overrides}
        self._put(doc_id, "document.html", html.encode(), "text/html")
        self._put(doc_id, "generated.json", {k: asdict(w) for k, w in written_for(slots, fresh, await self._documents.lookup()).items()})
        if source != c.source:
            self._put(doc_id, "source.json", asdict(source))
        return draft

    def delete(self, doc_id: str) -> None:
        keys = self._store.list(_prefix(doc_id))
        if not keys:
            raise SavedDocumentNotFound(doc_id)
        for key in keys:
            self._store.delete(key)
