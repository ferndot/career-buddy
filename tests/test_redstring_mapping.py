"""The redstring extraction path, through RedstringExtractor and a provider that returns a fixed answer."""

import asyncio
import json

import httpx

from career_graph.adapters.consolidation.redstring_candidates import skill_candidates
from career_graph.adapters.inference.redstring_extractor import RedstringExtractor
from career_graph.adapters.inference.structured_openai import StructuredOpenAIProvider
from career_graph.domain.model import Fact, FactBatch, FactKind, LinkKind
from career_graph.domain.profile import assemble_profile


class FixedProvider:
    """Stands in for the model: returns the same entities and relationships whatever the text."""

    model = "fixed"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def extract(self, text, schema, *, system_prompt=None):
        return schema.model_validate(self._payload)


def run_extract(payload: dict):
    return asyncio.run(RedstringExtractor(FixedProvider(payload)).extract("resume text", "resume.txt"))


def ent(name: str, kind: str) -> dict:
    return {"name": name, "entity_type": kind}


def rel(source: str, target: str, kind: str) -> dict:
    return {"source_name": source, "target_name": target, "relationship_type": kind}


def test_the_same_title_at_two_employers_stays_two_positions() -> None:
    batch = run_extract({
        "entities": [ent("Ada", "Person"), ent("Engineer at Acme", "Position"), ent("Engineer at Beta", "Position"),
                     ent("Acme", "Organization"), ent("Beta", "Organization")],
        "relationships": [rel("Ada", "Engineer at Acme", "HAS_POSITION"), rel("Ada", "Engineer at Beta", "HAS_POSITION"),
                          rel("Engineer at Acme", "Acme", "AT"), rel("Engineer at Beta", "Beta", "AT")],
    })
    positions = [f for f in batch.facts if f.kind == FactKind.POSITION]
    assert sorted((f.title, f.source) for f in positions) == [("Engineer", "resume.txt"), ("Engineer", "resume.txt")]
    employers = {l.target_id for l in batch.links if l.kind == LinkKind.AT}
    assert len(employers) == 2 and len(positions) == 2


def test_a_model_that_skips_the_person_links_still_gets_a_profile() -> None:
    batch = run_extract({
        "entities": [ent("Ada", "Person"), ent("Analyst at Royal Society", "Position"), ent("Royal Society", "Organization")],
        "relationships": [rel("Analyst at Royal Society", "Royal Society", "AT")],
    })
    profile = assemble_profile(batch)
    assert [p.title for p in profile.positions] == ["Analyst"]


def test_with_no_person_named_one_is_made_so_positions_still_show() -> None:
    batch = run_extract({"entities": [ent("Analyst at Royal Society", "Position"), ent("Royal Society", "Organization")],
                         "relationships": [rel("Analyst at Royal Society", "Royal Society", "AT")]})
    assert any(f.kind == FactKind.PERSON for f in batch.facts)
    assert assemble_profile(batch).positions[0].title == "Analyst"


def test_a_fenced_answer_is_read() -> None:
    answer = "```json\n" + json.dumps({"entities": [ent("Ada", "Person")], "relationships": []}) + "\n```"
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": answer}}]}))
    client = httpx.AsyncClient(base_url="http://model.test/v1/", transport=transport)
    batch = asyncio.run(RedstringExtractor(StructuredOpenAIProvider(client, "m")).extract("text", "src"))
    assert [f.title for f in batch.facts] == ["Ada"]


def test_hidden_skills_are_not_suggested_as_duplicates() -> None:
    batch = FactBatch((Fact("1", FactKind.SKILL, "Postgres"), Fact("2", FactKind.SKILL, "PostgreSQL", {"hidden": "true"})))
    assert asyncio.run(skill_candidates(batch)) == []
