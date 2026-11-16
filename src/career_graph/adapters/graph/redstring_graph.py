"""FactGraph adapter over redstring's in-memory GraphStore. Rebuilt from the event log at every start.

Facts are stored as redstring entities and links as relationships. The fact id is kept in `external_ids`, and the
entity id is derived from it, so every id in the event log still points at the same node after the move."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redstring import (
    Entity,
    ExtractionMethod,
    InMemoryGraphStore,
    Provenance,
    Relationship,
    SourceId,
    TenantId,
)

from career_graph.domain.model import Fact, FactBatch, FactKind, Link, LinkKind, normalize

TENANT = TenantId(uuid.uuid5(uuid.NAMESPACE_URL, "career-graph"))  # same tenant as the extractor


def _entity_id(fact_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"fact|{fact_id}")


def _link_id(link: Link) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{link.kind}|{link.source_id}|{link.target_id}")


class RedstringFactGraph:
    def __init__(self, store: InMemoryGraphStore | None = None) -> None:
        self._store = store or InMemoryGraphStore()
        self._order: dict[uuid.UUID, None] = {}  # first-seen order of entities, so snapshots list facts as imported

    async def apply(self, batch: FactBatch) -> None:
        now = datetime.now(UTC)
        await self._store.upsert_entities([self._entity(f, now) for f in batch.facts])
        self._order.update(dict.fromkeys(_entity_id(f.id) for f in batch.facts))
        known = set(self._order)  # links may reach facts from earlier batches; a link to an unknown fact is not stored
        links = [l for l in batch.links if _entity_id(l.source_id) in known and _entity_id(l.target_id) in known]
        await self._store.upsert_relationships([self._relationship(l) for l in links])

    async def snapshot(self) -> FactBatch:
        entities = [await self._store.get_entity(eid, TENANT) for eid in self._order]
        entities = [e for e in entities if e is not None]
        fact_of = {e.id: e.external_ids["fact"] for e in entities}
        facts = tuple(
            Fact(fact_of[e.id], FactKind(e.entity_type), e.name, {k: str(v) for k, v in e.properties.items()},
                 e.provenance.source_id or "")
            for e in entities
        )
        links: list[Link] = []
        for e in entities:
            for r in await self._store.get_relationships(e.id, TENANT, direction="out"):
                links.append(Link(fact_of[r.source_entity_id], fact_of[r.target_entity_id], LinkKind(r.relationship_type)))
        return FactBatch(facts, tuple(dict.fromkeys(links)))

    @staticmethod
    def _entity(fact: Fact, now: datetime) -> Entity:
        return Entity(
            id=_entity_id(fact.id),
            tenant_id=TENANT,
            external_ids={"fact": fact.id},
            name=fact.title,
            normalized_name=normalize(fact.title),
            entity_type=fact.kind.value,
            properties=dict(fact.attributes),
            # shortcut: every fact is recorded as a pattern-derived claim; the LLM/structured split is not kept per fact.
            provenance=Provenance(observed_at=now, extraction_method=ExtractionMethod.PATTERN, confidence=1.0,
                                  source_id=SourceId(fact.source)),
        )

    @staticmethod
    def _relationship(link: Link) -> Relationship:
        return Relationship(
            id=_link_id(link),
            tenant_id=TENANT,
            source_entity_id=_entity_id(link.source_id),
            target_entity_id=_entity_id(link.target_id),
            relationship_type=link.kind.value,
            confidence=1.0,
        )
