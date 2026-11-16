"""Saved documents: a rendered file and its metadata kept in the object store, under `documents/<id>/`."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from career_buddy.application.documents import DocumentService, TailorOptions
from career_buddy.application.ports import ObjectNotFound, ObjectStore
from career_buddy.domain.document import Style

_ID = re.compile(r"[0-9a-f]{32}")


class SavedDocumentNotFound(Exception):
    """No saved document has this id, or the id is not a valid one."""


@dataclass(frozen=True)
class SavedMeta:
    id: str
    label: str
    template: str
    format: str
    filename: str
    media_type: str
    created_at: str  # ISO 8601, UTC
    ats_issues: list[str]  # codes of the failed ATS checks at save time


def _prefix(doc_id: str) -> str:
    if not _ID.fullmatch(doc_id):
        raise SavedDocumentNotFound(doc_id)
    return f"documents/{doc_id}/"


class SavedDocuments:
    def __init__(self, store: ObjectStore, documents: DocumentService) -> None:
        self._store = store
        self._documents = documents

    async def save(self, template: str, fmt: str, style: Style, options: TailorOptions, label: str = "") -> SavedMeta:
        out = await self._documents.render(template, fmt, style, options)  # KeyError / RendererUnavailable pass through
        doc_id = uuid.uuid4().hex
        meta = SavedMeta(doc_id, label.strip() or PurePosixPath(out.filename).stem, template, fmt, out.filename, out.media_type,
                         datetime.now(UTC).isoformat(), [issue.code for issue in out.issues])
        prefix = _prefix(doc_id)
        ext = PurePosixPath(out.filename).suffix
        self._store.put(f"{prefix}file{ext}", out.data, out.media_type)
        self._store.put(f"{prefix}meta.json", json.dumps(asdict(meta)).encode(), "application/json")  # last: a record means a complete save
        return meta

    def _meta(self, doc_id: str) -> SavedMeta:
        try:
            return SavedMeta(**json.loads(self._store.get(f"{_prefix(doc_id)}meta.json")))
        except ObjectNotFound as error:
            raise SavedDocumentNotFound(doc_id) from error

    def list(self) -> list[SavedMeta]:
        keys = (k for k in self._store.list("documents/") if k.endswith("/meta.json"))
        metas = [SavedMeta(**json.loads(self._store.get(k))) for k in keys]
        return sorted(metas, key=lambda m: m.created_at, reverse=True)

    def get_file(self, doc_id: str) -> tuple[SavedMeta, bytes]:
        meta = self._meta(doc_id)
        try:
            return meta, self._store.get(f"{_prefix(doc_id)}file{PurePosixPath(meta.filename).suffix}")
        except ObjectNotFound as error:
            raise SavedDocumentNotFound(doc_id) from error

    def delete(self, doc_id: str) -> None:
        keys = self._store.list(_prefix(doc_id))
        if not keys:
            raise SavedDocumentNotFound(doc_id)
        for key in keys:
            self._store.delete(key)
