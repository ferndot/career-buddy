"""Commands change state (append an event, then project it). Queries only read the projection."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
from dataclasses import replace
from datetime import UTC, datetime

from career_buddy.application.jobs import READY, SourceJobs
from career_buddy.application.ports import (
    EventLog,
    FactExtractor,
    FactNotFound,
    NoOriginal,
    ObjectStore,
    SourceBusy,
    SourceNotFound,
    SourceParser,
    TextReader,
    UnreadableDocument,
    UnsupportedFileType,
)
from career_buddy.application.projector import Projector
from career_buddy.domain.dedup import merge_candidates
from career_buddy.domain.events import DuplicateDismissed, FactRevised, FactsImported, FactsMerged, SourceRemoved
from career_buddy.domain.manual import manual_fact
from career_buddy.domain.text import BULLETS
from career_buddy.domain.model import Fact, FactBatch, FactKind, InvalidFact
from career_buddy.domain.letter import write_letter
from career_buddy.domain.profile import Profile, assemble_profile, rank_for_job
from collections.abc import Awaitable, Callable


class ImportService:
    """Write side. Every import is recorded in the log before it reaches the graph.

    Text and file imports go through a job, so progress shows in the source list. With a model-backed extractor
    (`background`) the job runs after the call returns and `import_text` / `import_file` return None."""

    def __init__(
        self,
        log: EventLog,
        projector: Projector,
        parsers: dict[str, SourceParser],
        extractor: FactExtractor,
        file_readers: dict[str, TextReader],
        store: ObjectStore,
        jobs: SourceJobs,
        background: bool = False,
    ) -> None:
        self._log = log
        self._projector = projector
        self._parsers = parsers
        self._extractor = extractor
        self._file_readers = file_readers
        self._store = store
        self._jobs = jobs
        self._background = background

    async def _record(self, batch: FactBatch, source_key: str = "") -> int:
        event = FactsImported(batch, source_key)
        self._log.append(event)
        await self._projector.project(event)
        return len(batch.facts)

    async def import_structured(self, kind: str, files: dict[str, bytes], source: str) -> int:
        return await self._record(self._parsers[kind].parse(files, source))

    async def _extract_and_save(self, text: str, source: str, source_key: str, replace: bool) -> int:
        self._jobs.report(source, "Extracting positions", 30)
        batch = await self._extractor.extract(text, source)
        self._jobs.report(source, "Saving facts", 85)
        if replace:  # the old facts go first, so the new extraction replaces them instead of adding to them
            event = SourceRemoved(source, _now())
            self._log.append(event)
            await self._projector.project(event)
        count = await self._record(batch, source_key)
        await self._merge_duplicates()
        return count

    async def _merge_duplicates(self) -> None:
        """Merge the duplicates the matcher finds, each as a logged merge the user can undo. Dismissed pairs stay apart."""
        batch = await self._projector.snapshot()
        titles = {f.id: f.title for f in batch.facts}
        for a, b, _ in merge_candidates(batch):
            if a in self._projector.merges or b in self._projector.merges or frozenset((a, b)) in self._projector.dismissed:
                continue
            keep, drop = sorted((a, b), key=lambda i: (-len(titles[i]), i))  # the fuller name, e.g. "Acme Corp" over "Acme"
            event = FactsMerged(drop, keep, False, _now())
            self._log.append(event)
            await self._projector.project(event)

    async def import_text(self, text: str, source: str, source_key: str = "") -> int | None:
        """Facts added, or None when the work was queued."""
        key = source_key or await self._keep_original("txt", text.encode())  # kept so the source can be reindexed
        return await self._jobs.run(source, lambda: self._extract_and_save(text, source, key, False), self._background)

    async def _to_text(self, extension: str, data: bytes) -> str:
        reader = self._file_readers.get(extension)
        if reader is None:
            raise UnsupportedFileType(extension)
        extracted = await asyncio.to_thread(reader.read, data)  # PDF parsing is CPU-bound
        # Header text goes first: contact lines there are not part of any section.
        text = "\n".join(part for part in (extracted.header_footer_text, extracted.text) if part.strip())
        if not text.strip():
            raise UnreadableDocument("No text found in the file")
        return text

    async def import_file(self, extension: str, data: bytes, source: str) -> int | None:
        """Read a PDF, DOCX, TXT or MD to text, then take the same path as pasted text."""
        text = await self._to_text(extension, data)
        return await self.import_text(text, source, await self._keep_original(extension, data))

    def _original_key(self, source: str) -> str:
        keys = [e.source_key for e in self._log.replay()
                if isinstance(e, FactsImported) and e.source_key and any(f.source == source for f in e.batch.facts)]
        if not keys:
            raise NoOriginal(source)
        return keys[-1]

    async def reindex(self, source: str) -> None:
        """Read the stored original again and replace the source's facts with a fresh extraction. Always in the background."""
        if self._jobs.is_active(source):
            raise SourceBusy(source)
        if source not in self._projector.sources() and self._jobs.state(source) is None:
            raise SourceNotFound(source)
        key = self._original_key(source)

        async def work() -> int:
            self._jobs.report(source, "Reading file", 10)
            data = await asyncio.to_thread(self._store.get, key)
            text = await self._to_text(key.rsplit(".", 1)[-1], data)
            return await self._extract_and_save(text, source, key, True)

        await self._jobs.run(source, work, True)

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

    def __init__(self, log: EventLog, projector: Projector, jobs: SourceJobs, extractor: FactExtractor | None = None) -> None:
        self._log = log
        self._projector = projector
        self._jobs = jobs
        self._extractor = extractor  # reads a position's description into achievements

    async def _find(self, fact_id: str) -> Fact:
        facts = {f.id: f for f in (await self._projector.snapshot()).facts}
        if (fact := facts.get(fact_id)) is None:
            raise FactNotFound(fact_id)
        return fact

    async def _record(self, event: FactRevised | FactsImported | FactsMerged | DuplicateDismissed | SourceRemoved) -> None:
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

    async def remove_source(self, source: str) -> None:
        if self._jobs.is_active(source):
            raise SourceBusy(source)
        known = source in self._projector.sources()
        if not known and self._jobs.state(source) is None:
            raise FactNotFound(source)
        self._jobs.forget(source)
        if known:  # a source whose import failed has no facts and nothing in the log
            await self._record(SourceRemoved(source, _now()))

    async def add_fact(self, kind: FactKind, title: str, parent_id: str | None, attributes: dict[str, str]) -> str:
        """A position's description is read into achievements, by the model when one is configured, else line by line."""
        parent = await self._find(parent_id) if parent_id else None
        batch = manual_fact(kind, title, parent, attributes)
        achievements = await self._achievements(attributes.get("description", "")) if kind == FactKind.POSITION else []
        await self._record(FactsImported(batch))
        position = batch.facts[0]
        for text in achievements:
            await self._record(FactsImported(manual_fact(FactKind.ACHIEVEMENT, text, position, {})))
        return position.id

    async def _achievements(self, description: str) -> list[str]:
        """Read first, so a failed model call adds nothing rather than a half-entered position."""
        if not description.strip():
            return []
        if self._extractor is not None:
            batch = await self._extractor.extract(description, "manual")
            if found := [f.title for f in batch.facts if f.kind == FactKind.ACHIEVEMENT and f.title.strip()]:
                return found
        return [line.strip().lstrip("".join(BULLETS)).strip() for line in description.splitlines() if line.strip().lstrip("".join(BULLETS)).strip()]

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

    def __init__(self, graph: Projector, jobs: SourceJobs,
                 skill_matcher: Callable[[FactBatch], Awaitable[list[tuple[str, str, float]]]] | None = None) -> None:
        self._graph = graph
        self._jobs = jobs
        self._skill_matcher = skill_matcher  # finds skill duplicates; none means only organizations and positions

    async def profile(self) -> Profile:
        return assemble_profile(await self._graph.snapshot())

    async def sources(self) -> list[dict[str, object]]:
        batch = await self._graph.snapshot()
        counts: dict[str, int] = {}
        for f in batch.facts:
            counts[f.source] = counts.get(f.source, 0) + 1
        states = self._jobs.states()  # a queued or failed import has no facts yet, so it is listed from here
        out = []
        for name in sorted(self._graph.sources() | states.keys()):
            state = states.get(name, READY)  # no entry: imported before this run, so it is ready
            out.append({"source": name, "facts": counts.get(name, 0), "status": state.status,
                        "progress": state.progress, "step": state.step, "error": state.error})
        return out

    async def source(self, name: str) -> dict[str, object]:
        return next(s for s in await self.sources() if s["source"] == name)

    async def graph(self) -> dict[str, list[dict[str, object]]]:
        batch = await self._graph.snapshot()
        return {
            "nodes": [{"id": f.id, "kind": f.kind.value, "title": f.title, "source": f.source} for f in batch.facts],
            "edges": [{"source": l.source_id, "target": l.target_id, "kind": l.kind.value} for l in batch.links],
        }

    async def facts(self, kind: FactKind | None = None) -> list[dict[str, object]]:
        batch = await self._graph.snapshot()
        return [fact_json(f) for f in batch.facts if kind is None or f.kind == kind]

    async def duplicates(self) -> list[dict[str, object]]:
        batch = await self._graph.snapshot()
        by_id = {f.id: f for f in batch.facts}
        found = merge_candidates(batch)
        if self._skill_matcher:
            found = sorted(found + await self._skill_matcher(batch), key=lambda c: (-c[2], c[0], c[1]))
        return [
            {"kind": by_id[a].kind, "a": {"id": a, "title": by_id[a].title}, "b": {"id": b, "title": by_id[b].title},
             "score": round(score, 3)}
            for a, b, score in found
            if frozenset((a, b)) not in self._graph.dismissed
        ]

    async def cover_letter(self, job_text: str) -> str:
        return write_letter(await self.profile(), job_text)

    async def fit(self, job_text: str) -> dict[str, object]:
        positions, skills = rank_for_job(await self.profile(), job_text)
        return {"positions": [p.title for p in positions], "matched_skills": skills}
