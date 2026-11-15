"""One `project(event)` path for live commands and for replay at startup.

The graph holds what was imported. Revisions and merges are overlaid when reading, so the result
does not depend on event order: a revision beats any import of the same id, before or after it.
"""

from __future__ import annotations

from dataclasses import replace

from career_graph.application.ports import FactGraph
from career_graph.domain.events import DuplicateDismissed, Event, FactRevised, FactsImported, FactsMerged
from career_graph.domain.model import FactBatch, Link


class Projector:
    def __init__(self, graph: FactGraph) -> None:
        self._graph = graph
        self._revisions: dict[str, FactRevised] = {}
        self.merges: dict[str, str] = {}  # alias id -> canonical id
        self.dismissed: set[frozenset[str]] = set()  # pairs the user said are not the same

    async def project(self, event: Event) -> None:
        match event:
            case FactsImported(batch):
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

    def _resolve(self, fact_id: str) -> str:
        seen = {fact_id}
        while (target := self.merges.get(fact_id)) and target not in seen:
            fact_id = target
            seen.add(fact_id)
        return fact_id

    async def snapshot(self) -> FactBatch:
        raw = await self._graph.snapshot()
        facts = tuple(
            replace(f, title=r.title, attributes=r.attributes) if (r := self._revisions.get(f.id)) else f
            for f in raw.facts
            if f.id not in self.merges
        )
        links = dict.fromkeys(
            Link(self._resolve(l.source_id), self._resolve(l.target_id), l.kind) for l in raw.links
        )
        return FactBatch(facts, tuple(l for l in links if l.source_id != l.target_id))
