"""Skill category, years and level, and an achievement's result, survive extraction into the facts response."""

import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from llm_support import connect_mock

POSITION = "Engineer at Acme"
ADA = {"name": "Ada", "entity_type": "Person"}


class Model:
    """The LLM behind the mocked transport: answers with `entities` (plus the person, the position and its links)."""

    def __init__(self) -> None:
        self.extra: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        entities = [ADA, {"name": POSITION, "entity_type": "Position"}, {"name": "Acme", "entity_type": "Organization"}, *self.extra]
        rels = [{"source_name": "Ada", "target_name": POSITION, "relationship_type": "HAS_POSITION"},
                {"source_name": POSITION, "target_name": "Acme", "relationship_type": "AT"}]
        rels += [{"source_name": "Ada", "target_name": e["name"], "relationship_type": "HAS_SKILL"}
                 for e in self.extra if e["entity_type"] == "Skill"]
        rels += [{"source_name": POSITION, "target_name": e["name"], "relationship_type": "ACHIEVED"}
                 for e in self.extra if e["entity_type"] == "Achievement"]
        content = json.dumps({"entities": entities, "relationships": rels})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: Model):
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)
    with TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model))) as c:
        connect_mock(c)
        yield c


def import_text(client: TestClient, source: str) -> None:
    client.post("/api/import/text", json={"text": "Ada\nSkills\nPython, Go", "source": source})
    deadline = time.monotonic() + 5
    while client.get("/api/sources").json() and any(s["status"] != "ready" for s in client.get("/api/sources").json()):
        assert time.monotonic() < deadline
        time.sleep(0.02)


def facts(client: TestClient, kind: str) -> dict[str, dict]:
    return {f["title"]: f["attributes"] for f in client.get("/api/facts", params={"kind": kind}).json()}


def skill(name: str, **props: str) -> dict:
    return {"name": name, "entity_type": "Skill", "properties": props}


def test_an_extracted_skill_keeps_its_stated_category_years_and_level(client, model) -> None:
    model.extra = [skill("Python", category="Languages", years="5+", level="Expert"), skill("AWS", category="Cloud")]
    import_text(client, "a.txt")
    found = facts(client, "Skill")
    assert found["Python"] == {"category": "Languages", "years": "5+", "level": "Expert"}
    assert found["AWS"] == {"category": "Cloud"}


def test_a_skill_keeps_its_category_when_another_source_states_it_differently(client, model) -> None:
    model.extra = [skill("Python", category="Languages")]
    import_text(client, "a.txt")
    model.extra = [skill("Python", category="Other")]
    import_text(client, "b.txt")
    assert facts(client, "Skill")["Python"]["category"] == "Languages"


def test_an_achievement_keeps_its_result_exactly_and_a_missing_one_is_fine(client, model) -> None:
    model.extra = [{"name": "Cut build time", "entity_type": "Achievement", "properties": {"result": "from 45 min to 6 min (-87%)"}},
                   {"name": "Ran the team", "entity_type": "Achievement"}]
    import_text(client, "a.txt")
    found = facts(client, "Achievement")
    assert found["Cut build time"] == {"result": "from 45 min to 6 min (-87%)"}
    assert found["Ran the team"] == {}


def test_a_manual_achievement_carries_its_result(client) -> None:
    client.post("/api/import/file", files={"file": ("r.txt", b"Jane Doe\n\nExperience\nLead at Acme, 2020 - 2021\n- Ran it\n", "text/plain")})
    position = next(f for f in client.get("/api/facts", params={"kind": "Position"}).json())
    res = client.post("/api/facts", json={"kind": "Achievement", "title": "Cut costs", "parent_id": position["id"],
                                          "attributes": {"result": "saved $1.2M / yr"}})
    assert res.status_code == 201
    assert facts(client, "Achievement")["Cut costs"] == {"result": "saved $1.2M / yr"}


def test_tools_an_achievement_names_become_skills_the_position_uses(client, model) -> None:
    model.extra = [skill("Python", category="Languages"),
                   {"name": "Cut build time", "entity_type": "Achievement", "properties": {"result": "-87%", "tools": "Python, Docker; Bazel"}}]
    import_text(client, "a.txt")
    found = facts(client, "Skill")
    assert found["Python"] == {"category": "Languages"}  # one skill, and the stated category stays
    assert found["Docker"] == found["Bazel"] == {"category": "Tools & platforms"}
    assert facts(client, "Achievement")["Cut build time"] == {"result": "-87%"}  # tools are not kept on the achievement
    used = next(p for p in client.get("/api/profile").json()["positions"] if p["title"] == "Engineer")
    assert {"Python", "Docker", "Bazel"} <= set(used["skills"])
    graph = client.get("/api/graph").json()
    title = {n["id"]: n["title"] for n in graph["nodes"]}
    uses = {(title[e["source"]], title[e["target"]]) for e in graph["edges"] if e["kind"] == "USES_SKILL"}
    assert {("Cut build time", "Python"), ("Cut build time", "Docker"), ("Cut build time", "Bazel"), ("Engineer", "Docker")} <= uses
