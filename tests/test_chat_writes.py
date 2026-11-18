"""The career chat's write tools (POST /api/chat): add, edit and delete a fact. A write is proposed as an AG-UI interrupt and runs only in the next run, from
a resume entry that is resolved with approved true. Everything is checked through the stream and the public facts route."""

import json

import pytest
from fastapi.testclient import TestClient

from test_chat_api import career, chat, results, text  # noqa: F401  (career is a fixture)


def facts(client: TestClient) -> dict[str, dict]:
    return {f["title"]: f for f in client.get("/api/facts").json()}


def proposal(name: str, args: dict) -> list[dict]:
    """The transcript a client sends back after the model proposed a write: the user's message and the assistant's open tool call."""
    call = {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    return [{"id": "m1", "role": "user", "content": "please"}, {"id": "m2", "role": "assistant", "toolCalls": [call]}]


def answer(client: TestClient, name: str, args: dict, resume: list[dict] | None) -> list[dict]:
    body = {"threadId": "t", "runId": "r", "state": {}, "tools": [], "context": [], "forwardedProps": {}, "messages": proposal(name, args)}
    if resume is not None:
        body["resume"] = resume
    client.script("Done.")  # type: ignore[attr-defined]
    response = client.post("/api/chat", json=body)
    return [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]


APPROVED = [{"interruptId": "c1", "status": "resolved", "payload": {"approved": True}}]
SENIOR = {"title": "Staff Engineer"}


def test_a_proposed_write_ends_the_run_with_an_interrupt_that_shows_the_change_and_changes_nothing(career: TestClient) -> None:
    before = career.get("/api/facts").json()
    model = career.script(("edit_fact", {"fact_id": career.ids["Senior Engineer"], "title": "Staff Engineer", "changes": {"started": "2018-03"}}), "unused")  # type: ignore[attr-defined]
    events = chat(career, "Make me Staff Engineer")
    finished = events[-1]
    assert finished["type"] == "RUN_FINISHED" and finished["outcome"]["type"] == "interrupt"
    [interrupt] = finished["outcome"]["interrupts"]
    assert interrupt["reason"] == "tool_call" and interrupt["toolCallId"] == interrupt["id"] == "call1"
    assert interrupt["message"] == "Position 'Senior Engineer': title 'Senior Engineer' -> 'Staff Engineer'; started '2019-03' -> '2018-03'"
    assert results(events) == [] and len(model.requests) == 1  # the run stopped: no result, no second model call
    assert career.get("/api/facts").json() == before


def test_an_approved_write_changes_the_facts_and_the_model_is_told(career: TestClient) -> None:
    events = answer(career, "edit_fact", {"fact_id": career.ids["Senior Engineer"], **SENIOR}, APPROVED)
    assert results(events) == ["Changed: Position 'Senior Engineer': title 'Senior Engineer' -> 'Staff Engineer'"]
    assert events[-1]["type"] == "RUN_FINISHED" and not events[-1].get("outcome")
    assert "Staff Engineer" in facts(career) and "Senior Engineer" not in facts(career)


@pytest.mark.parametrize("resume", [[{"interruptId": "c1", "status": "resolved", "payload": {"approved": False}}],
                                    [{"interruptId": "c1", "status": "cancelled"}],
                                    [{"interruptId": "other", "status": "resolved", "payload": {"approved": True}}],
                                    [{"interruptId": "c1", "status": "resolved", "payload": {"approved": "yes"}}],
                                    None],
                         ids=["declined", "cancelled", "other id", "not a true", "no resume at all"])
def test_a_write_without_an_approval_is_refused_and_changes_nothing(career: TestClient, resume: list[dict] | None) -> None:
    before = career.get("/api/facts").json()
    events = answer(career, "delete_fact", {"fact_id": career.ids["Senior Engineer"]}, resume)
    assert results(events) == ["Declined by the user."]
    assert career.get("/api/facts").json() == before


def test_the_model_reads_the_decision_in_its_next_request(career: TestClient) -> None:
    model = career.script("ok")  # type: ignore[attr-defined]
    body = {"threadId": "t", "runId": "r", "state": {}, "tools": [], "context": [], "forwardedProps": {},
            "messages": proposal("edit_fact", {"fact_id": career.ids["Senior Engineer"], **SENIOR}), "resume": APPROVED}
    career.post("/api/chat", json=body)
    tool = model.requests[0]["messages"][-1]
    assert tool["role"] == "tool" and tool["tool_call_id"] == "c1" and tool["content"].startswith("Changed: Position 'Senior Engineer'")


def test_add_an_achievement_under_a_position_and_a_skill_under_the_person(career: TestClient) -> None:
    position = career.ids["Senior Engineer"]
    events = answer(career, "add_fact", {"kind": "Achievement", "title": "Halved the cloud bill", "parent_id": position}, APPROVED)
    assert results(events) == ["Changed: Add Achievement 'Halved the cloud bill' under Position 'Senior Engineer'"]
    answer(career, "add_fact", {"kind": "Skill", "title": "Terraform"}, APPROVED)
    shown = career.get("/api/graph").json()
    nodes = {n["id"]: n["title"] for n in shown["nodes"]}
    assert ("Senior Engineer", "Halved the cloud bill") in {(nodes[e["source"]], nodes[e["target"]]) for e in shown["edges"] if e["kind"] == "ACHIEVED"}
    assert ("Jane Doe", "Terraform") in {(nodes[e["source"]], nodes[e["target"]]) for e in shown["edges"] if e["kind"] == "HAS_SKILL"}


def test_a_new_positions_description_is_not_read_into_achievements(career: TestClient) -> None:
    answer(career, "add_fact", {"kind": "Position", "title": "CTO", "attributes": {"organization": "Initech", "description": "Ran everything\nHired everyone"}}, APPROVED)
    assert "CTO" in facts(career) and "Ran everything" not in facts(career)


def test_edit_the_summary_keeps_every_attribute_the_change_does_not_mention(career: TestClient) -> None:
    person = facts(career)["Jane Doe"]
    answer(career, "edit_fact", {"fact_id": person["id"], "changes": {"summary": "Builds platforms", "location": ""}}, APPROVED)
    after = facts(career)["Jane Doe"]["attributes"]
    assert after["summary"] == "Builds platforms" and after["headline"] == person["attributes"]["headline"] and "location" not in after


def test_delete_a_fact_for_good(career: TestClient) -> None:
    achievement = career.ids["Cut build times by 60%"]
    answer(career, "delete_fact", {"fact_id": achievement}, APPROVED)
    assert "Cut build times by 60%" not in facts(career)


@pytest.mark.parametrize("call", [("delete_fact", {"fact_id": "nope"}), ("edit_fact", {"fact_id": "nope", "title": "x"}), ("add_fact", {"kind": "Achievement", "title": "x"}),
                                  ("add_fact", {"kind": "Hobby", "title": "x"}), ("edit_fact", {"fact_id": "unused"})])
def test_a_write_that_cannot_be_made_is_a_failed_result_not_an_approval_card(career: TestClient, call: tuple[str, dict]) -> None:
    name, args = call
    if args["fact_id" if "fact_id" in args else "title"] == "unused":
        args = {"fact_id": career.ids["Senior Engineer"]}  # no title and no changes: nothing to approve
    career.script((name, args), "Sorry.")  # type: ignore[attr-defined]
    before = career.get("/api/facts").json()
    events = chat(career)
    assert results(events)[0].startswith("Failed:") and text(events) == "Sorry." and events[-1].get("outcome") is None
    assert career.get("/api/facts").json() == before
