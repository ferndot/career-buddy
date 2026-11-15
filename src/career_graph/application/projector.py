"""One `project(event)` path for live commands and for replay at startup.

The graph holds what was imported. Revisions, merges and removed sources are overlaid when reading, so the
result does not depend on event order: a revision beats any import of the same id, before or after it.
"""

from __future__ import annotations

from dataclasses import replace

from career_graph.application.ports import FactGraph
from career_graph.domain.events import DuplicateDismissed, Event, FactRevised, FactsImported, FactsMerged, SourceRemoved
from career_graph.domain.model import FactBatch, Link


class Projector:
    def __init__(self, graph: FactGraph) -> None:
        self._graph = graph
        self._revisions: dict[str, FactRevised] = {}
        self._stated_by: dict[str, set[str]] = {}  # fact id -> every source that imported it
        self.merges: dict[str, str] = {}  # alias id -> canonical id
        self.dismissed: set[frozenset[str]] = set()  # pairs the user said are not the same
        self.removed: set[str] = set()  # sources the user removed

    async def project(self, event: Event) -> None:
        match event:
            case FactsImported(batch):
                for fact in batch.facts:
                    self._stated_by.setdefault(fact.id, set()).add(fact.source)
                self.removed.difference_update({f.source for f in batch.facts})  # re-importing brings a source back
                await self._graph.apply(batch)
            case FactRevised():
                self._revisions[event.fact_id] = event
            case FactsMerged(alias_id, canonical_id, undo):
                if undo:
                    self.merges.pop(alias_id, None)
                else:
                    self.merges[alias_id] = canonical_id
            case DuplicateDismissed(a_id, b_id):
                self.dismissed.add(frozenset((a_id, b_id)))
            case SourceRemoved(source):
                self.removed.add(source)

    def sources(self) -> set[str]:
        """Sources still in use: imported and not removed."""
        return {s for stated in self._stated_by.values() for s in stated} - self.removed

    def _resolve(self, fact_id: str) -> str:
        seen = {fact_id}
        while (target := self.merges.get(fact_id)) and target not in seen:
            fact_id = target
            seen.add(fact_id)
        return fact_id

    async def snapshot(self) -> FactBatch:
        raw = await self._graph.snapshot()
        visible = {}
        for f in raw.facts:
            if f.id in self.merges:
                continue
            live = self._stated_by.get(f.id, {f.source}) - self.removed
            if not live:
                continue
            source = f.source if f.source in live else min(live)
            revision = self._revisions.get(f.id)
            visible[f.id] = replace(
                f,
                title=revision.title if revision else f.title,
                attributes=revision.attributes if revision else f.attributes,
                source=source,
            )
        links = dict.fromkeys(
            Link(self._resolve(l.source_id), self._resolve(l.target_id), l.kind) for l in raw.links
        )
        return FactBatch(
            tuple(visible.values()),
            tuple(l for l in links if l.source_id != l.target_id and l.source_id in visible and l.target_id in visible),
        )
