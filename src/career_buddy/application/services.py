"""Commands change state (append an event, then project it). Queries only read the projection."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
from dataclasses import replace
from datetime import UTC, datetime

from career_buddy.application.jobs import READY, SourceJobs
from career_buddy.application.ports import (
    EventLog,
    FactExtractor,
    FactNotFound,
    JobReviewer,
    LLMUnavailable,
    NoOriginal,
    ObjectStore,
    SourceBusy,
    SourceNotFound,
    TextReader,
    UnreadableDocument,
    UnsupportedFileType,
)
from career_buddy.application.projector import Projector
from career_buddy.domain.dates import checked
from career_buddy.domain.dedup import auto_merges, canonical_of, merge_candidates
from career_buddy.domain.events import (
    DuplicateDismissed,
    FactDeleted,
    FactRevised,
    FactsImported,
    FactsMerged,
    LinkAdded,
    LinkRemoved,
    SourceRegistered,
    SourceRemoved,
)
from career_buddy.domain.manual import manual_fact
from career_buddy.domain.text import BULLETS
from career_buddy.domain.model import Fact, FactBatch, FactKind, InvalidFact, Link, LinkKind
from career_buddy.domain.generation import MAX_POSTING
from career_buddy.domain.profile import Profile, assemble_profile
from career_buddy.domain.review import fact_text, uncovered, validate
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)


class ImportService:
    """Write side. Every import is recorded in the log before it reaches the graph.

    Text and file imports go through a job, so progress shows in the source list. With a model-backed extractor
    (`background`) the job runs after the call returns and `import_text` / `import_file` return None."""

    def __init__(
        self,
        log: EventLog,
        projector: Projector,
        extractor: FactExtractor,
        file_readers: dict[str, TextReader],
        store: ObjectStore,
        jobs: SourceJobs,
        background: bool = False,
    ) -> None:
        self._log = log
        self._projector = projector
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

    async def _extract_and_save(self, text: str, source: str, source_key: str) -> int:
        """Additive: a fact already in the graph keeps its edits and merges, a new one is added. Near-certain duplicates are merged (and logged), the rest only suggested."""
        self._jobs.report(source, "Extracting career facts")
        batch = await self._extractor.extract(text, source)
        self._jobs.report(source, "Saving facts")
        count = await self._record(batch, source_key)
        await self._merge_certain_duplicates()
        return count

    async def _merge_certain_duplicates(self) -> None:
        """Merge the pairs at or above the auto-merge bar as logged `auto` merges. A merge can expose
        more pairs (positions of merged employers), so go on until none is left. Undone and dismissed pairs stay apart."""
        projector = self._projector
        while True:
            batch = await projector.snapshot()
            touched = projector.revised | {f.id for f in batch.facts if f.source == "manual"}
            apart = await projector.dismissed_now() | {frozenset((e.alias_id, e.canonical_id)) for e in self._log.replay()
                                                      if isinstance(e, FactsMerged) and e.undo}
            pairs = auto_merges(batch, merge_candidates(batch), touched, apart)
            if not pairs:
                return
            titles = {f.id: f.title for f in batch.facts}
            for alias, canonical in pairs:
                event = FactsMerged(alias, canonical, False, _now(), True)
                self._log.append(event)
                await projector.project(event)
                log.info("Merged duplicate %r into %r", titles[alias], titles[canonical])

    async def import_text(self, text: str, source: str, source_key: str = "") -> int | None:
        """Facts added, or None when the work was queued."""
        key = source_key or await self._keep_original("txt", text.encode())  # kept so the source can be reindexed
        event = SourceRegistered(source, key, _now())  # before the job, so a failed first run can still be retried
        self._log.append(event)
        await self._projector.project(event)
        return await self._jobs.run(source, lambda: self._extract_and_save(text, source, key), self._background)

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
                if (isinstance(e, SourceRegistered) and e.source == source)
                or (isinstance(e, FactsImported) and e.source_key and any(f.source == source for f in e.batch.facts))]
        if not keys:
            raise NoOriginal(source)
        return keys[-1]

    async def reindex(self, source: str) -> None:
        """Read the stored original again and add what a fresh extraction finds; earlier facts and the user's edits stay. Always in the background."""
        if self._jobs.is_active(source):
            raise SourceBusy(source)
        if source not in self._projector.sources():
            raise SourceNotFound(source)
        key = self._original_key(source)

        async def work() -> int:
            self._jobs.report(source, "Reading file")
            data = await asyncio.to_thread(self._store.get, key)
            text = await self._to_text(key.rsplit(".", 1)[-1], data)
            return await self._extract_and_save(text, source, key)

        await self._jobs.run(source, work, True)

    async def _keep_original(self, extension: str, data: bytes) -> str:
        """Content-addressed, so the same file is stored once however often or under whatever name it is uploaded."""
        key = f"sources/{hashlib.sha256(data).hexdigest()}.{extension}"
        if not await asyncio.to_thread(self._store.exists, key):
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            await asyncio.to_thread(self._store.put, key, data, content_type)
        return key


# The links the user may add and remove, with the kinds of their (source, target).
EDITABLE_LINKS = {
    "AT": ((FactKind.POSITION, FactKind.ORGANIZATION),),
    "ATTENDED": ((FactKind.EDUCATION, FactKind.ORGANIZATION),),
    "USES_SKILL": ((FactKind.POSITION, FactKind.SKILL), (FactKind.ACHIEVEMENT, FactKind.SKILL)),
    "ACHIEVED": ((FactKind.POSITION, FactKind.ACHIEVEMENT),),
}


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

    async def _record(
        self, event: FactRevised | FactsImported | FactsMerged | DuplicateDismissed | SourceRemoved | FactDeleted | LinkAdded | LinkRemoved
    ) -> None:
        self._log.append(event)
        await self._projector.project(event)

    async def delete(self, fact_id: str) -> None:
        await self._find(fact_id)
        await self._record(FactDeleted(fact_id, _now()))

    async def _link(self, source_id: str, target_id: str, kind: str) -> tuple[Link, bool]:
        """The link the user means and whether it is in the graph now. Unknown facts are FactNotFound; other kinds InvalidFact."""
        allowed = EDITABLE_LINKS.get(kind)
        if allowed is None:
            raise InvalidFact(f"Links of kind {kind!r} cannot be edited")
        source, target = await self._find(source_id), await self._find(target_id)
        if (source.kind, target.kind) not in allowed:
            raise InvalidFact(f"{kind} links " + " or ".join(f"a {a} to a {b}" for a, b in allowed))
        link = Link(source_id, target_id, LinkKind(kind))
        return link, link in (await self._projector.snapshot()).links

    async def add_link(self, source_id: str, target_id: str, kind: str) -> None:
        link, present = await self._link(source_id, target_id, kind)
        if not present:  # adding a link that exists is a no-op
            await self._record(LinkAdded(source_id, target_id, kind, _now()))

    async def remove_link(self, source_id: str, target_id: str, kind: str) -> None:
        link, present = await self._link(source_id, target_id, kind)
        if not present:
            raise FactNotFound(f"{source_id} -> {target_id} ({kind})")  # the 404 handler's "Unknown fact" is close enough
        await self._record(LinkRemoved(source_id, target_id, kind, _now()))

    async def revise(self, fact_id: str, title: str | None, attributes: dict[str, str] | None) -> Fact:
        """Full replacement of title and attributes. An omitted field keeps its current value."""
        fact = await self._find(fact_id)
        title = fact.title if title is None else title.strip()
        if not title:
            raise InvalidFact("Title is empty")
        revised = replace(fact, title=title, attributes=fact.attributes if attributes is None else checked(attributes))
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
                 skill_matcher: Callable[[FactBatch], Awaitable[list[tuple[str, str, float]]]] | None = None,
                 reviewer: JobReviewer | None = None) -> None:
        self._reviewer = reviewer  # reads job postings; none means no model is connected
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
        dismissed = await self._graph.dismissed_now()
        touched = self._graph.revised | {f.id for f in batch.facts if f.source == "manual"}  # the user's own work is what a merge keeps
        return [
            {"kind": by_id[a].kind, "a": {"id": a, "title": by_id[a].title}, "b": {"id": b, "title": by_id[b].title},
             "score": round(score, 3), "canonical_id": canonical_of(by_id[a], by_id[b], touched)}
            for a, b, score in found
            if frozenset((a, b)) not in dismissed
        ]

    async def fit(self, job_text: str) -> dict[str, object]:
        """The model's review of the posting, validated against it, and which of its terms no fact covers. Only the posting is sent.

        LLMUnavailable: no model is connected, or it did not answer. There is no keyword fallback."""
        if self._reviewer is None:
            raise LLMUnavailable("Connect a model in Settings to check the job posting for requirements.")
        posting = job_text.strip()[:MAX_POSTING]
        review = validate(await self._reviewer.review(posting), posting)
        facts = fact_text(await self.profile())
        return {"title": review.title, "company": review.company, "must_have": list(review.must_have),
                "nice_to_have": list(review.nice_to_have), "missing_must_have": list(uncovered(review.must_have, facts)),
                "missing_nice_to_have": list(uncovered(review.nice_to_have, facts))}
