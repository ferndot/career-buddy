"""Saved documents, kept in the object store under `documents/<id>/`.

A saved document is live. It keeps a layout of restricted HTML plus CSS (`document.html`, `document.css`), what the user
wrote (`overrides.json`, by slot id), what a writer wrote (`generated.json`) and what it was built from (`source.json`:
the settings). The text of every other slot is found when the document is read (domain/slots.py), so a
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
from career_buddy.domain.generation import ResumeLength
from career_buddy.domain.markers import clean_document
from career_buddy.domain.slots import Slot, Written, layout_overrides, resolve, written_for
from career_buddy.domain.templates import Layout, get_template
from career_buddy.domain.written import WrittenDocument, blank_letter, texts

_ID = re.compile(r"[0-9a-f]{32}")
DEFAULT_FORMAT = "docx"


@dataclass(frozen=True)
class HtmlCodec:
    """How a document is kept: written to a layout in html and css, read back with the text of each slot."""

    write: Callable[[Document, Layout], str]
    css: Callable[[Style, Layout], str]
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
    """What a document was built from: the job, the inputs and the directions. No text of its own."""

    template: str
    job_text: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    instructions: str = ""  # the user's directions for the writer
    resume_pages: ResumeLength = "default"  # how long a resume should be
    template_instructions: str = ""  # the template's and the chosen style's instructions for the writer

    @staticmethod
    def of(template: str, options: TailorOptions, instructions: str, resume_pages: ResumeLength, template_instructions: str = "") -> SavedSource:
        return SavedSource(template, options.job_text, options.inputs, instructions, resume_pages, template_instructions)

    def options(self, overrides: dict[str, str]) -> TailorOptions:
        return TailorOptions(self.job_text, overrides, self.inputs)


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

    async def _document(self, template: str, html: str, overrides: Mapping[str, str], generated: Mapping[str, Written]) -> Document:
        """The layout read with its slots resolved against the facts as they are now, in the template's page arrangement."""
        texts = resolve(self._html.slots(html), overrides, await self._documents.lookup(), generated)
        return replace(clean_document(self._html.read(html, texts, frozenset(overrides)))[0], layout=get_template(template).layout)

    async def _layout(self, template: str, options: TailorOptions, written: WrittenDocument | None) -> tuple[str, str]:
        """The layout html and the file stem. With `written`, the layout is its sections: the structure the writer chose, each text a slot.
        Without, it is the template filled from the facts. KeyError: unknown template."""
        if not (written and written.sections) and get_template(template).kind == "letter":
            written = blank_letter(options.overrides)  # a letter the person wrote themselves
        doc, stem = await self._documents.compose(template, options, written if written and written.sections else None)
        return self._html.write(doc, get_template(template).layout), stem

    def _put(self, doc_id: str, name: str, data: object, content_type: str = "application/json") -> None:
        self._store.put(f"{_prefix(doc_id)}{name}", data if isinstance(data, bytes) else json.dumps(data).encode(), content_type)

    async def save(self, template: str, style: Style, options: TailorOptions, label: str = "",
                   written: WrittenDocument | None = None, instructions: str = "", resume_pages: ResumeLength = "default",
                   template_instructions: str = "") -> SavedMeta:
        """Keep the layout, what the user wrote (`options.overrides`, by slot id or fact id), what a writer wrote (`written`: its sections are
        the layout, its texts `generated.json`) and what the document was built from. The facts' own text is not kept: it is found when
        the document is read."""
        html, stem = await self._layout(template, options, written)
        slots = self._html.slots(html)
        overrides = layout_overrides(options.overrides, (slot.id for slot in slots))
        made = written_for(slots, texts(written) if written else {}, await self._documents.lookup())
        issues = (await self._documents.export(await self._document(template, html, overrides, made), DEFAULT_FORMAT, style, stem)).issues
        doc_id = uuid.uuid4().hex
        meta = SavedMeta(doc_id, label.strip() or stem, template, stem, datetime.now(UTC).isoformat(),
                         [issue.code for issue in issues], style.font, style.paper)
        self._put(doc_id, "document.html", html.encode(), "text/html")
        self._put(doc_id, "document.css", self._html.css(style, get_template(template).layout).encode(), "text/css")
        self._put(doc_id, "overrides.json", overrides)
        self._put(doc_id, "generated.json", {k: asdict(w) for k, w in made.items()})
        self._put(doc_id, "source.json", asdict(SavedSource.of(template, options, instructions.strip(), resume_pages, template_instructions.strip())))
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
                            SavedSource(**{**source, "resume_pages": 1 if source.get("resume_pages") == 1 else "default"}) if source else None)  # a stored 2 or 3 is the default

    async def slots(self, doc_id: str) -> dict[str, str]:
        """The text of every slot as it reads now: override, generated text, the facts, then the placeholder."""
        c = self.content(doc_id)
        return resolve(self._html.slots(c.html), c.overrides, await self._documents.lookup(), c.generated)

    async def download(self, doc_id: str, fmt: str | None = None) -> Rendered:
        """The file: the layout with its slots resolved now, converted to `fmt` (default docx)."""
        c = self.content(doc_id)
        doc = await self._document(c.meta.template, c.html, c.overrides, c.generated)
        return await self._documents.export(doc, fmt or DEFAULT_FORMAT, Style(c.meta.font, c.meta.paper), c.meta.filename)  # type: ignore[arg-type]

    async def regenerate(self, doc_id: str, instructions: str = "", resume_pages: ResumeLength | None = None) -> Draft:
        """Write the text again from the facts as they are now. It replaces generated text only: a slot with an override is
        pinned, left to the writer untouched, and keeps the user's words. NoSource: saved before sources were kept.
        LLMUnavailable and UngroundedDraft as for DocumentGeneration."""
        c = self.content(doc_id)
        if c.source is None:
            raise NoSource(doc_id)
        source = replace(c.source, instructions=instructions.strip() or c.source.instructions, resume_pages=resume_pages or c.source.resume_pages)
        options = source.options(c.overrides)
        draft = await self._generation.generate(source.template, options, source.instructions, c.overrides, source.resume_pages, source.template_instructions)
        html, _ = await self._layout(source.template, options, draft.doc)
        slots = self._html.slots(html)
        fresh = {k: v for k, v in texts(draft.doc).items() if k not in c.overrides}
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
