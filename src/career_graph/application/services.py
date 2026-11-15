"""Commands change state (append an event, then project it). Queries only read the projection."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
from dataclasses import replace
from datetime import UTC, datetime

from career_graph.application.ports import (
    EventLog,
    FactExtractor,
    FactNotFound,
    ObjectStore,
    SourceParser,
    TextReader,
    UnreadableDocument,
    UnsupportedFileType,
)
from career_graph.application.projector import Projector
from career_graph.domain.dedup import merge_candidates
from career_graph.domain.events import DuplicateDismissed, FactRevised, FactsImported, FactsMerged
from career_graph.domain.manual import manual_fact
from career_graph.domain.model import Fact, FactBatch, FactKind, InvalidFact
from career_graph.domain.letter import write_letter
from career_graph.domain.profile import Profile, assemble_profile, rank_for_job


class ImportService:
    """Write side. Every import is recorded in the log before it reaches the graph."""

    def __init__(
        self,
        log: EventLog,
        projector: Projector,
        parsers: dict[str, SourceParser],
        extractor: FactExtractor,
        file_readers: dict[str, TextReader],
        store: ObjectStore,
    ) -> None:
        self._log = log
        self._projector = projector
        self._parsers = parsers
        self._extractor = extractor
        self._file_readers = file_readers
        self._store = store

    async def _record(self, batch: FactBatch, source_key: str = "") -> int:
        event = FactsImported(batch, source_key)
        self._log.append(event)
        await self._projector.project(event)
        return len(batch.facts)

    async def import_structured(self, kind: str, files: dict[str, bytes], source: str) -> int:
        return await self._record(self._parsers[kind].parse(files, source))

    async def import_text(self, text: str, source: str, source_key: str = "") -> int:
        return await self._record(await self._extractor.extract(text, source), source_key)

    async def import_file(self, extension: str, data: bytes, source: str) -> int:
        """Read a PDF, DOCX, TXT or MD to text, then take the same path as pasted text."""
        reader = self._file_readers.get(extension)
        if reader is None:
            raise UnsupportedFileType(extension)
        extracted = await asyncio.to_thread(reader.read, data)  # PDF parsing is CPU-bound
        # Header text goes first: contact lines there are not part of any section.
        text = "\n".join(part for part in (extracted.header_footer_text, extracted.text) if part.strip())
        if not text.strip():
            raise UnreadableDocument("No text found in the file")
        return await self.import_text(text, source, await self._keep_original(extension, data))

    async def _keep_original(self, extension: str, data: bytes) -> str:
        """Content-addressed, so the same file is stored once however often or under whatever name it is uploaded."""
        key = f"sources/{hashlib.sha256(data).hexdigest()}.{extension}"
        if not await asyncio.to_thread(self._store.exists, key):
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            await asyncio.to_thread(self._store.put, key, data, content_type)
        return key


def _now() -> str:
    return datetime.now(UTC).isoformat()


def fact_json(f: Fact) -> dict[str, object]:
    return {"id": f.id, "kind": f.kind, "title": f.title, "attributes": f.attributes, "source": f.source}


class EditService:
    """Write side for the user's own changes: revise, add by hand, merge. Each is logged, then projected."""

    def __init__(self, log: EventLog, projector: Projector) -> None:
        self._log = log
        self._projector = projector

    async def _find(self, fact_id: str) -> Fact:
        facts = {f.id: f for f in (await self._projector.snapshot()).facts}
        if (fact := facts.get(fact_id)) is None:
            raise FactNotFound(fact_id)
        return fact

    async def _record(self, event: FactRevised | FactsImported | FactsMerged | DuplicateDismissed) -> None:
        self._log.append(event)
        await self._projector.project(event)

    async def revise(self, fact_id: str, title: str | None, attributes: dict[str, str] | None) -> Fact:
        """Full replacement of title and attributes. An omitted field keeps its current value."""
        fact = await self._find(fact_id)
        title = fact.title if title is None else title.strip()
        if not title:
            raise InvalidFact("Title is empty")
        revised = replace(fact, title=title, attributes=fact.attributes if attributes is None else attributes)
        await self._record(FactRevised(fact_id, revised.title, revised.attributes, _now()))
        return revised

    async def set_order(self, fact_id: str, order: int) -> Fact:
        fact = await self._find(fact_id)
        return await self.revise(fact_id, None, {**fact.attributes, "order": str(order)})

    async def dismiss(self, a_id: str, b_id: str) -> None:
        """Record that two facts are not the same. Both must exist."""
        if a_id == b_id:
            raise InvalidFact("A fact is not a duplicate of itself")
        await self._find(a_id), await self._find(b_id)
        await self._record(DuplicateDismissed(a_id, b_id, _now()))

    async def add_fact(self, kind: FactKind, title: str, parent_id: str | None, attributes: dict[str, str]) -> str:
        parent = await self._find(parent_id) if parent_id else None
        batch = manual_fact(kind, title, parent, attributes)
        await self._record(FactsImported(batch))
        return batch.facts[0].id

    async def merge(self, alias_id: str, canonical_id: str, undo: bool) -> None:
        if alias_id == canonical_id:
            raise InvalidFact("A fact cannot be merged into itself")
        if undo:
            if self._projector.merges.get(alias_id) != canonical_id:
                raise FactNotFound(alias_id)
        else:
            alias, canonical = await self._find(alias_id), await self._find(canonical_id)
            if alias.kind != canonical.kind:
                raise InvalidFact("Only facts of the same kind can be merged")
        await self._record(FactsMerged(alias_id, canonical_id, undo, _now()))


class CareerQueries:
    """Read side. Assembles views from the projection; never writes."""

    def __init__(self, graph: Projector) -> None:
        self._graph = graph

    async def profile(self) -> Profile:
        return assemble_profile(await self._graph.snapshot())

    async def facts(self, kind: FactKind | None = None) -> list[dict[str, object]]:
        batch = await self._graph.snapshot()
        return [fact_json(f) for f in batch.facts if kind is None or f.kind == kind]

    async def duplicates(self) -> list[dict[str, object]]:
        batch = await self._graph.snapshot()
        by_id = {f.id: f for f in batch.facts}
        return [
            {"kind": by_id[a].kind, "a": {"id": a, "title": by_id[a].title}, "b": {"id": b, "title": by_id[b].title},
             "score": round(score, 3)}
            for a, b, score in merge_candidates(batch)
            if frozenset((a, b)) not in self._graph.dismissed
        ]

    async def cover_letter(self, job_text: str) -> str:
        return write_letter(await self.profile(), job_text)

    async def fit(self, job_text: str) -> dict[str, object]:
        positions, skills = rank_for_job(await self.profile(), job_text)
        return {"positions": [p.title for p in positions], "matched_skills": skills}
