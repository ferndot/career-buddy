"""Saved documents, kept in the object store under `documents/<id>/`.

A document is kept as restricted HTML plus CSS (`document.html`, `document.css`, `overrides.json`) and converted to the
requested format at download time.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from career_buddy.application.documents import DocumentService, Rendered, TailorOptions
from career_buddy.application.ports import ObjectNotFound, ObjectStore
from career_buddy.domain.document import Document, Style

_ID = re.compile(r"[0-9a-f]{32}")
DEFAULT_FORMAT = "docx"


@dataclass(frozen=True)
class HtmlCodec:
    """How a document is kept: written to html and css, read back from html with its slot overrides."""

    write: Callable[[Document], str]
    css: Callable[[Style], str]
    read: Callable[[str, dict[str, str]], Document]


class SavedDocumentNotFound(Exception):
    """No saved document has this id, or the id is not a valid one."""


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


def _prefix(doc_id: str) -> str:
    if not _ID.fullmatch(doc_id):
        raise SavedDocumentNotFound(doc_id)
    return f"documents/{doc_id}/"


def _parse(raw: bytes) -> SavedMeta:
    return SavedMeta(**json.loads(raw))


class SavedDocuments:
    def __init__(self, store: ObjectStore, documents: DocumentService, html: HtmlCodec) -> None:
        self._store = store
        self._documents = documents
        self._html = html

    async def save(self, template: str, style: Style, options: TailorOptions, label: str = "") -> SavedMeta:
        doc, stem = await self._documents.compose(template, options)  # KeyError: unknown template
        issues = (await self._documents.export(doc, DEFAULT_FORMAT, style, stem)).issues
        doc_id = uuid.uuid4().hex
        meta = SavedMeta(doc_id, label.strip() or stem, template, stem, datetime.now(UTC).isoformat(),
                         [issue.code for issue in issues], style.font, style.paper)
        prefix = _prefix(doc_id)
        self._store.put(f"{prefix}document.html", self._html.write(doc).encode(), "text/html")
        self._store.put(f"{prefix}document.css", self._html.css(style).encode(), "text/css")
        self._store.put(f"{prefix}overrides.json", b"{}", "application/json")
        self._store.put(f"{prefix}meta.json", json.dumps(asdict(meta)).encode(), "application/json")  # last: a record means a complete save
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

    def _overrides(self, doc_id: str) -> dict[str, str]:
        try:
            return json.loads(self._store.get(f"{_prefix(doc_id)}overrides.json"))
        except ObjectNotFound:
            return {}

    def content(self, doc_id: str) -> tuple[SavedMeta, str, str, dict[str, str]]:
        """The stored html and css and the slot overrides."""
        meta = self._meta(doc_id)
        return meta, self._read(doc_id, "document.html").decode(), self._read(doc_id, "document.css").decode(), self._overrides(doc_id)

    async def download(self, doc_id: str, fmt: str | None = None) -> Rendered:
        """The file: converted from the stored html in `fmt` (default docx)."""
        meta, html, _, overrides = self.content(doc_id)
        doc = self._html.read(html, overrides)
        return await self._documents.export(doc, fmt or DEFAULT_FORMAT, Style(meta.font, meta.paper), meta.filename)  # type: ignore[arg-type]

    def delete(self, doc_id: str) -> None:
        keys = self._store.list(_prefix(doc_id))
        if not keys:
            raise SavedDocumentNotFound(doc_id)
        for key in keys:
            self._store.delete(key)
