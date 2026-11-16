"""Skill duplicate candidates from redstring's CandidateFinder: blocking, then similarity scoring over the skill names.

Suggestions only. Nothing here merges; the user confirms each pair through FactsMerged."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redstring import CandidateFinder, Entity, ExtractionMethod, InMemoryGraphStore, Provenance, SourceId, TenantId
from redstring.domain.blocking import blocking_keys_for

from career_buddy.domain.model import FactBatch, FactKind, is_hidden, normalize

THRESHOLD = 0.85  # "Postgres" vs "PostgreSQL" scores 0.96; "JS" vs "JavaScript" scores 0.76 and needs an alias, not a lower bar
TENANT = TenantId(uuid.uuid5(uuid.NAMESPACE_URL, "career-buddy-candidates"))


def _entity_id(fact_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"skill|{fact_id}")


async def skill_candidates(batch: FactBatch) -> list[tuple[str, str, float]]:
    """(id, id, score) pairs of skills whose names are similar, smaller id first, best score first."""
    skills = {f.id: f for f in batch.facts if f.kind == FactKind.SKILL and not is_hidden(f)}
    if len(skills) < 2:
        return []
    store = InMemoryGraphStore()
    entities = []
    for fact in skills.values():
        entity = Entity(
            id=_entity_id(fact.id), tenant_id=TENANT, external_ids={"fact": fact.id}, name=fact.title,
            normalized_name=normalize(fact.title), entity_type="Skill",
            provenance=Provenance(observed_at=_EPOCH, extraction_method=ExtractionMethod.PATTERN, confidence=1.0,
                                  source_id=SourceId(fact.source)),
        )
        entities.append(entity.model_copy(update={"blocking_keys": blocking_keys_for(entity)}))
    await store.upsert_entities(entities)

    finder = CandidateFinder(store)
    pairs: dict[tuple[str, str], float] = {}
    for entity in entities:
        for found in await finder.candidates(entity, minimum_score=THRESHOLD):
            a, b = sorted((entity.external_ids["fact"], found.entity.external_ids["fact"]))
            if a != b:
                pairs[a, b] = max(pairs.get((a, b), 0.0), round(found.score, 3))
    return sorted(((a, b, s) for (a, b), s in pairs.items()), key=lambda c: (-c[2], c[0], c[1]))


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)  # a fixed instant: candidate scoring does not read provenance times
