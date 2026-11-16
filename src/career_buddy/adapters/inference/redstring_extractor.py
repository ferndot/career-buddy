"""FactExtractor backed by redstring's ExtractionPipeline and the career domain schema.

redstring finds entities and relationships; this module turns them into career facts. Fact ids keep the
career-buddy scheme (kind, title, scope), so the same claim from two sources still merges into one fact."""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
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

from career_buddy.adapters.inference.errors import unavailable
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind, fact_id

log = logging.getLogger("career_buddy.extraction.pipeline")
CAREER_SCHEMA: Path = Path(__file__).with_name("career_schema.yaml")
TENANT = TenantId(uuid.uuid5(uuid.NAMESPACE_URL, "career-buddy"))  # one person, one tenant
OWNER_LINK = {FactKind.POSITION: LinkKind.HAS_POSITION, FactKind.EDUCATION: LinkKind.HAS_EDUCATION,
              FactKind.SKILL: LinkKind.HAS_SKILL}


class _LoggedProvider:
    """Wraps a provider so every chunk's answer shows in the log: an empty answer reads the same as a good one downstream."""

    def __init__(self, inner: LlmProvider) -> None:
        self._inner = inner
        self._chunks = 0  # one wrapper per extraction, so this counts that document's chunks

    @property
    def model(self) -> str:
        return self._inner.model

    async def extract[S: BaseModel](self, text: str, schema: type[S], *, system_prompt: str | None = None) -> S:
        self._chunks += 1
        number = self._chunks
        log.info("chunk %d: asking the model about %d characters", number, len(text))
        answer = await self._inner.extract(text, schema, system_prompt=system_prompt)
        entities = getattr(answer, "entities", None)
        if entities is None:  # not an extraction answer (e.g. a gleaning or rewrite schema)
            return answer
        log.info("chunk %d of %d characters (starts %r): the model listed %d entities and %d relationships",
                 number, len(text), text[:40], len(entities), len(getattr(answer, "relationships", ())))
        if not entities:
            log.warning("chunk of %d characters (starts %r): the model listed no entities, so nothing was taken from it",
                        len(text), text[:40])
        return answer


class RedstringExtractor:
    def __init__(self, provider: LlmProvider, schema: DomainSchema | None = None) -> None:
        schema = schema or load_schema_from_file(CAREER_SCHEMA)
        self._model = provider.model
        self._provider = provider
        self._prompt = domain_system_prompt(schema)

    async def extract(self, text: str, source: str) -> FactBatch:
        document = SourceDocument(id=SourceId(source), text=text)
        log.info("extracting %s: %d characters, model %s", source, len(text), self._model)
        try:
            pipeline = ExtractionPipeline(_LoggedProvider(self._provider), system_prompt=self._prompt)
            result = await pipeline.extract(document, TENANT, observed_at=datetime.now(UTC))
        except RedstringError as error:
            log.warning("extracting %s failed (model %s): %s", source, self._model, error)
            raise unavailable(error) from error
        log.info("%s: %d chunk(s), %d failed; entities %s; relationships %s; redstring dropped %d entities, "
                 "%d relationships with an unlisted end, %d self-loops",
                 source, result.total_chunks, result.failed_chunks,
                 dict(Counter(e.entity_type for e in result.entities)),
                 dict(Counter(r.relationship_type for r in result.relationships)),
                 result.dropped_entities, result.unresolved_relationships, result.self_loops)
        if result.failed_chunks:
            log.warning("%s: %d of %d chunks failed and were skipped", source, result.failed_chunks, result.total_chunks)
        return to_batch(result, source)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _target_names(result: PipelineResult, rel: LinkKind) -> dict[object, str]:
    """Source entity id -> name of the target, for one relationship type (e.g. AT: position -> employer)."""
    by_id = {e.id: e for e in result.entities}
    return {r.source_entity_id: _text(by_id[r.target_entity_id].name)
            for r in result.relationships if _link_kind(r.relationship_type) == rel and r.target_entity_id in by_id}


def to_batch(result: PipelineResult, source: str) -> FactBatch:
    """Map redstring entities and relationships to career facts. Logs what it could not map, and why."""
    org_of = _target_names(result, LinkKind.AT)
    school_of = _target_names(result, LinkKind.ATTENDED)
    position_of = {r.target_entity_id: r.source_entity_id for r in result.relationships
                   if _link_kind(r.relationship_type) == LinkKind.ACHIEVED}
    by_id = {e.id: e for e in result.entities}

    dropped: Counter[str] = Counter()  # why an entity or relationship did not become a fact or link
    fact_of: dict[object, str] = {}
    facts: dict[str, Fact] = {}
    for entity in result.entities:
        kind = _kind(entity)
        if kind is None:
            dropped[f"entity type {entity.entity_type!r}"] += 1
            continue
        title = _title(entity, kind, org_of)
        scope = _scope(kind, entity.id, org_of, school_of, position_of, by_id)
        fid = fact_id(kind, title, scope)
        fact_of[entity.id] = fid
        if fid in facts:
            dropped["same kind, title and scope as another fact"] += 1
        facts.setdefault(fid, Fact(fid, kind, title, _attributes(entity), source))

    links: dict[Link, None] = {}
    for r in result.relationships:
        if (kind := _link_kind(r.relationship_type)) is None:
            dropped[f"relationship type {r.relationship_type!r}"] += 1
            continue
        s, t = fact_of.get(r.source_entity_id), fact_of.get(r.target_entity_id)
        if s and t and s != t:
            links[Link(s, t, kind)] = None
        else:
            dropped["relationship to itself" if s and t else "relationship end is not a fact"] += 1
    made_person = _attach_to_person(facts, links, source)
    _log_mapping(source, result, facts, links, dropped, made_person)
    return FactBatch(tuple(facts.values()), tuple(links))


def _log_mapping(source: str, result: PipelineResult, facts: dict, links: dict, dropped: Counter[str], made_person: bool) -> None:
    summary = "%s: %d facts %s and %d links from %d entities and %d relationships"
    args = (source, len(facts), dict(Counter(f.kind.value for f in facts.values())), len(links),
            len(result.entities), len(result.relationships))
    if dropped:
        log.warning(summary + "; dropped: %s", *args, dict(dropped))
    else:
        log.info(summary, *args)
    if made_person and len(facts) == 1:
        log.warning("%s: no career entity came back, so the only fact is the placeholder person. Check the chunk lines "
                    "above (empty answers) and any dropped reasons.", source)


def _attach_to_person(facts: dict[str, Fact], links: dict[Link, None], source: str) -> bool:
    """A career has one person. A model that skips the person's links still gets a profile: attach to the first Person,
    or make one. True when one was made."""
    people = [f.id for f in facts.values() if f.kind == FactKind.PERSON]
    made = not people
    if made:
        person = fact_id(FactKind.PERSON, "Me")
        facts[person] = Fact(person, FactKind.PERSON, "Me", {}, source)
        people = [person]
    owned = {(l.target_id, l.kind) for l in links}
    for f in list(facts.values()):
        if (kind := OWNER_LINK.get(f.kind)) and (f.id, kind) not in owned:
            links[Link(people[0], f.id, kind)] = None
    return made


def _kind(entity: Entity) -> FactKind | None:
    """Models spell the type as they like ('position', 'Skills '); matching ignores case and padding."""
    return next((k for k in FactKind if k.value.lower() == entity.entity_type.strip().lower()), None)


def _link_kind(name: str) -> LinkKind | None:
    return next((k for k in LinkKind if k.value == name.strip().upper()), None)


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
