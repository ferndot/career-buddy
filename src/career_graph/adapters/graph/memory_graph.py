"""FactGraph adapter: a plain in-memory store (plan D7). Rebuilt from the event log at every start."""

from __future__ import annotations

from career_graph.domain.model import Fact, FactBatch, Link


class MemoryFactGraph:
    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._links: dict[Link, None] = {}  # dict as an insertion-ordered set

    async def apply(self, batch: FactBatch) -> None:
        for fact in batch.facts:
            self._facts[fact.id] = fact
        self._links.update(dict.fromkeys(batch.links))

    async def snapshot(self) -> FactBatch:
        return FactBatch(tuple(self._facts.values()), tuple(self._links))
