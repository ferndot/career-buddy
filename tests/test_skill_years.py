"""A skill's years is a whole number of 0 or more, or empty: checked on add and edit through the routes and on the chat tool's proposal."""

import pytest
from fastapi.testclient import TestClient

from test_chat_api import career, chat, results, text  # noqa: F401  (career is a fixture)


def add(client: TestClient, years: str):
    person = client.get("/api/facts", params={"kind": "Person"}).json()[0]["id"]
    return client.post("/api/facts", json={"kind": "Skill", "title": "Rust", "parent_id": person, "attributes": {"years": years}})


@pytest.mark.parametrize("years", ["5+", "abc", "-1", "3 years", "2.5"])
def test_adding_a_skill_refuses_years_that_are_not_a_whole_number(career: TestClient, years: str) -> None:
    res = add(career, years)
    assert res.status_code == 422 and "whole number" in res.text


@pytest.mark.parametrize("years", ["0", "5", "120", ""])
def test_adding_a_skill_accepts_whole_years_or_none(career: TestClient, years: str) -> None:
    assert add(career, years).status_code == 201


def test_editing_years_is_checked(career: TestClient) -> None:
    skill = add(career, "5").json()["id"]
    assert career.patch(f"/api/facts/{skill}", json={"attributes": {"years": "5+"}}).status_code == 422
    assert career.patch(f"/api/facts/{skill}", json={"attributes": {"years": "6"}}).status_code == 200


def test_the_chat_tool_refuses_a_non_integer_with_its_reason_and_no_approval_card(career: TestClient) -> None:
    career.script(("add_fact", {"kind": "Skill", "title": "Rust", "attributes": {"years": "5+"}}), "Sorry.")  # type: ignore[attr-defined]
    events = chat(career)
    assert "whole number" in results(events)[0] and events[-1].get("outcome") is None


def test_the_model_is_told_how_to_call_edit_fact(career: TestClient) -> None:
    model = career.script("Hi.")  # type: ignore[attr-defined]
    chat(career)
    system = model.requests[0]["messages"][0]["content"]
    tool = next(t["function"]["description"] for t in model.requests[0]["tools"] if t["function"]["name"] == "edit_fact")
    assert "never invent" in system and "never text" in tool and "no maximum" in system and "ask before calling" in system and "Skill: title is its name; fields category, years (a whole number of 0 or more, never text), level" in system + tool


def test_a_refused_edit_returns_its_reason_and_no_card(career: TestClient) -> None:
    skill = add(career, "5").json()["id"]
    career.script(("edit_fact", {"fact_id": skill, "changes": {"years": "5+"}}), "Sorry.")  # type: ignore[attr-defined]
    events = chat(career)
    assert "whole number" in results(events)[0] and events[-1].get("outcome") is None
    assert next(f for f in career.get("/api/facts", params={"kind": "Skill"}).json() if f["id"] == skill)["attributes"]["years"] == "5"


def test_the_edit_fields_come_from_the_career_schema_and_years_is_a_whole_number_without_a_maximum() -> None:
    from career_buddy.adapters.inference.career_fields import MANUAL_FIELDS, edit_fields, field_guide, schema_fields
    from career_buddy.adapters.inference.redstring_extractor import CAREER_SCHEMA

    schema = schema_fields()
    for kind, names in edit_fields().items():  # a field edit_fact offers is in the schema, or is a declared hand-written one
        assert all(n in schema.get(kind, {}) or n in MANUAL_FIELDS.get(kind, []) for n in names)
    assert not set(MANUAL_FIELDS["Position"]) & set(schema["Position"])
    assert schema["Skill"]["years"] == "number" and "whole number of 0 or more, never text" in field_guide()
    text = CAREER_SCHEMA.read_text(encoding="utf-8")
    assert "no maximum" in text and "maximum:" not in text  # the schema has no integer type or bounds; the domain check is the integer rule
