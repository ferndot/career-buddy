"""FactExtractor backed by redstring's ExtractionPipeline and the career domain schema.

redstring finds entities and relationships; this module turns them into career facts. Fact ids keep the
career-graph scheme (kind, title, scope), so the same claim from two sources still merges into one fact."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from redstring import (
    DomainSchema,
    Entity,
    ExtractionPipeline,
    LlmProvider,
    PipelineResult,
    RedstringError,
    SourceDocument,
    SourceId,
    TenantId,
    domain_system_prompt,
    load_schema_from_file,
)

from career_graph.adapters.inference.errors import unavailable
from career_graph.domain.model import Fact, FactBatch, FactKind, Link, LinkKind, fact_id

CAREER_SCHEMA: Path = Path(__file__).with_name("career_schema.yaml")
TENANT = TenantId(uuid.uuid5(uuid.NAMESPACE_URL, "career-graph"))  # one person, one tenant
OWNER_LINK = {FactKind.POSITION: LinkKind.HAS_POSITION, FactKind.EDUCATION: LinkKind.HAS_EDUCATION,
              FactKind.SKILL: LinkKind.HAS_SKILL}


class RedstringExtractor:
    def __init__(self, provider: LlmProvider, schema: DomainSchema | None = None) -> None:
        schema = schema or load_schema_from_file(CAREER_SCHEMA)
        self._pipeline = ExtractionPipeline(provider, system_prompt=domain_system_prompt(schema))

    async def extract(self, text: str, source: str) -> FactBatch:
        document = SourceDocument(id=SourceId(source), text=text)
        try:
            result = await self._pipeline.extract(document, TENANT, observed_at=datetime.now(UTC))
        except RedstringError as error:
            raise unavailable(error) from error
        return to_batch(result, source)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _target_names(result: PipelineResult, rel: str) -> dict[object, str]:
    """Source entity id -> name of the target, for one relationship type (e.g. AT: position -> employer)."""
    by_id = {e.id: e for e in result.entities}
    return {r.source_entity_id: _text(by_id[r.target_entity_id].name)
            for r in result.relationships if r.relationship_type == rel and r.target_entity_id in by_id}


def to_batch(result: PipelineResult, source: str) -> FactBatch:
    """Map redstring entities and relationships to career facts. Pure."""
    org_of = _target_names(result, "AT")
    school_of = _target_names(result, "ATTENDED")
    position_of = {r.target_entity_id: r.source_entity_id for r in result.relationships if r.relationship_type == "ACHIEVED"}
    by_id = {e.id: e for e in result.entities}

    fact_of: dict[object, str] = {}
    facts: dict[str, Fact] = {}
    for entity in result.entities:
        kind = _kind(entity)
        if kind is None:
            continue
        title = _title(entity, kind, org_of)
        scope = _scope(kind, entity.id, org_of, school_of, position_of, by_id)
        fid = fact_id(kind, title, scope)
        fact_of[entity.id] = fid
        facts.setdefault(fid, Fact(fid, kind, title, _attributes(entity), source))

    links: dict[Link, None] = {}
    for r in result.relationships:
        if (kind := _link_kind(r.relationship_type)) is None:
            continue
        s, t = fact_of.get(r.source_entity_id), fact_of.get(r.target_entity_id)
        if s and t and s != t:
            links[Link(s, t, kind)] = None
    _attach_to_person(facts, links, source)
    return FactBatch(tuple(facts.values()), tuple(links))


def _attach_to_person(facts: dict[str, Fact], links: dict[Link, None], source: str) -> None:
    """A career has one person. A model that skips the person's links still gets a profile: attach to the first Person, or make one."""
    people = [f.id for f in facts.values() if f.kind == FactKind.PERSON]
    if not people:
        person = fact_id(FactKind.PERSON, "Me")
        facts[person] = Fact(person, FactKind.PERSON, "Me", {}, source)
        people = [person]
    owned = {(l.target_id, l.kind) for l in links}
    for f in list(facts.values()):
        if (kind := OWNER_LINK.get(f.kind)) and (f.id, kind) not in owned:
            links[Link(people[0], f.id, kind)] = None


def _kind(entity: Entity) -> FactKind | None:
    return next((k for k in FactKind if k.value == entity.entity_type), None)


def _link_kind(name: str) -> LinkKind | None:
    return next((k for k in LinkKind if k.value == name), None)


def _title(entity: Entity, kind: FactKind, org_of: dict) -> str:
    """The schema asks for 'Title at Organization' so same-title jobs stay apart; the title is the part before it."""
    name, org = _text(entity.name), org_of.get(entity.id, "")
    if kind == FactKind.POSITION and org and name.endswith(f" at {org}"):
        return name[: -len(f" at {org}")].strip()
    return name


def _scope(kind: FactKind, entity_id: object, org_of: dict, school_of: dict, position_of: dict, by_id: dict) -> str:
    """Scopes mirror BatchBuilder: a position belongs to its employer, an achievement to its position."""
    if kind == FactKind.POSITION:
        return org_of.get(entity_id, "")
    if kind == FactKind.EDUCATION:
        return school_of.get(entity_id, "")
    if kind == FactKind.ACHIEVEMENT and (pos := by_id.get(position_of.get(entity_id))):
        return f"{_title(pos, FactKind.POSITION, org_of)}|{org_of.get(pos.id, '')}"
    return ""


def _attributes(entity: Entity) -> dict[str, str]:
    attrs = {k: _text(v) for k, v in entity.properties.items() if _text(v)}
    if entity.temporal and entity.temporal.original_text:
        attrs.setdefault("period", _text(entity.temporal.original_text))
    return attrs
