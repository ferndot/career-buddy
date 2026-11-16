"""One `project(event)` path for live commands and for replay at startup.

The graph holds what was imported. Revisions, merges and removed sources are overlaid when reading, so the
result does not depend on event order: a revision beats any import of the same id, before or after it.
"""

from __future__ import annotations

from dataclasses import replace

from career_buddy.application.ports import FactGraph
from career_buddy.domain.events import (
    DuplicateDismissed,
    Event,
    FactDeleted,
    FactRevised,
    FactsImported,
    FactsMerged,
    LinkAdded,
    LinkRemoved,
    SourceRegistered,
    SourceRemoved,
)
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind


class Projector:
    def __init__(self, graph: FactGraph) -> None:
        self._graph = graph
        self._revisions: dict[str, FactRevised] = {}
        self._stated_by: dict[str, set[str]] = {}  # fact id -> every source that imported it
        self.merges: dict[str, str] = {}  # alias id -> canonical id
        self.dismissed: set[frozenset[str]] = set()  # pairs the user said are not the same
        self.removed: set[str] = set()  # sources the user removed
        self._registered: set[str] = set()  # sources imported, with or without facts
        self.deleted: set[str] = set()  # facts the user deleted for good; a re-import does not bring them back
        self._link_overrides: dict[Link, bool] = {}  # the user's last word on a link: True present, False removed; in event order

    async def project(self, event: Event) -> None:
        match event:
            case FactsImported(batch):
                for fact in batch.facts:
                    self._stated_by.setdefault(fact.id, set()).add(fact.source)
                self.removed.difference_update({f.source for f in batch.facts})  # re-importing brings a source back
                await self._graph.apply(await self._keep_categories(batch))
            case SourceRegistered(source):
                self._registered.add(source)
                self.removed.discard(source)  # importing again brings a removed source back
            case FactRevised():
                self._revisions[event.fact_id] = event
            case FactsMerged(alias_id, canonical_id, undo):
                if undo:
                    self.merges.pop(alias_id, None)
                else:
                    self.merges[alias_id] = canonical_id
            case DuplicateDismissed(a_id, b_id):
                self.dismissed.add(frozenset((a_id, b_id)))
            case FactDeleted(fact_id):
                self.deleted.add(fact_id)
            case LinkAdded() | LinkRemoved():
                link = Link(event.source_id, event.target_id, LinkKind(event.kind))
                self._link_overrides.pop(link, None)  # re-insert, so the last event is the last in order
                self._link_overrides[link] = isinstance(event, LinkAdded)
            case SourceRemoved(source):
                self.removed.add(source)
                for stated in self._stated_by.values():  # forget it, so a later import of the source replaces its facts
                    stated.discard(source)

    async def _keep_categories(self, batch: FactBatch) -> FactBatch:
        """A skill already in the graph keeps its category: a later import (often a model's guess) does not overwrite it."""
        have = {f.id: f.attributes["category"] for f in (await self._graph.snapshot()).facts
                if f.kind == FactKind.SKILL and f.attributes.get("category")}
        keep = lambda f: replace(f, attributes={**f.attributes, "category": have[f.id]}) if f.id in have else f  # noqa: E731
        return replace(batch, facts=tuple(map(keep, batch.facts))) if have else batch

    def sources(self) -> set[str]:
        """Sources still in use: imported and not removed."""
        return ({s for stated in self._stated_by.values() for s in stated} | self._registered) - self.removed

    def _live(self, raw: FactBatch) -> set[str]:
        """Ids some source still states. A merge into anything else is inert: the alias shows again."""
        return {f.id for f in raw.facts if self._stated_by.get(f.id, {f.source}) - self.removed}

    def _resolve(self, fact_id: str, live: set[str]) -> str:
        seen = {fact_id}
        while (target := self.merges.get(fact_id)) and target in live and target not in seen:
            fact_id = target
            seen.add(fact_id)
        return fact_id

    @property
    def revised(self) -> set[str]:
        """Ids of facts the user has edited."""
        return set(self._revisions)

    async def dismissed_now(self) -> set[frozenset[str]]:
        """The dismissed pairs as the snapshot shows them: each end resolved through merges, so a merge does not bring a pair back."""
        live = self._live(await self._graph.snapshot())
        return {frozenset(self._resolve(i, live) for i in pair) for pair in self.dismissed}

    async def absorbed(self) -> dict[str, list[Fact]]:
        """Canonical fact id -> the alias facts merged into it. Their own wording and details are not in the snapshot."""
        raw = await self._graph.snapshot()
        live = self._live(raw)
        out: dict[str, list[Fact]] = {}
        for f in raw.facts:
            if f.id in live and (canonical := self._resolve(f.id, live)) != f.id:
                out.setdefault(canonical, []).append(f)
        return out

    async def snapshot(self) -> FactBatch:
        raw = await self._graph.snapshot()
        alive = self._live(raw)
        resolve = lambda i: self._resolve(i, alive)  # noqa: E731
        visible = {}
        for f in raw.facts:
            if f.id not in alive or resolve(f.id) != f.id:
                continue
            live = self._stated_by.get(f.id, {f.source}) - self.removed
            source = f.source if f.source in live else min(live)
            revision = self._revisions.get(f.id)
            visible[f.id] = replace(
                f,
                title=revision.title if revision else f.title,
                attributes=revision.attributes if revision else f.attributes,
                source=source,
            )
        links = dict.fromkeys(
            Link(resolve(l.source_id), resolve(l.target_id), l.kind) for l in raw.links
        )
        for l, present in self._link_overrides.items():  # resolved like the rest, so a later merge keeps the edit
            link = Link(resolve(l.source_id), resolve(l.target_id), l.kind)
            links.pop(link, None)
            if present:
                links[link] = None
        # Deleting a position takes its achievements with it: they belong to the position. Links go with their ends.
        for gone in self.deleted | {l.target_id for l in links if l.kind == LinkKind.ACHIEVED and l.source_id in self.deleted}:
            visible.pop(gone, None)
        return FactBatch(
            tuple(visible.values()),
            tuple(l for l in links if l.source_id != l.target_id and l.source_id in visible and l.target_id in visible),
        )
