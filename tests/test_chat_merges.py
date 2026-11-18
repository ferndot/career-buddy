"""The career chat's merge, relationship and source tools (POST /api/chat): approved, declined and refused. Like the other write tools, each is proposed as an
interrupt and runs only from a resolved, approved resume entry. Everything is read back through the public routes and the list_merges tool."""

import json

import pytest
from fastapi.testclient import TestClient

from test_chat_api import career, chat, results, text  # noqa: F401  (career is a fixture)
from test_chat_writes import APPROVED, answer


def state(client: TestClient) -> tuple:
    return client.get("/api/facts").json(), client.get("/api/graph").json(), client.get("/api/sources").json()


def edges(client: TestClient) -> set[tuple[str, str, str]]:
    nodes = {n["id"]: n["title"] for n in client.get("/api/graph").json()["nodes"]}
    return {(nodes[e["source"]], nodes[e["target"]], e["kind"]) for e in client.get("/api/graph").json()["edges"]}


def merges(client: TestClient) -> list[tuple[str, str]]:
    client.script(("list_merges", {}), "ok")  # type: ignore[attr-defined]
    return [(m["alias"]["title"], m["canonical"]["title"]) for m in json.loads(results(chat(client))[0])]


def skill(client: TestClient, title: str) -> str:
    return client.post("/api/facts", json={"kind": "Skill", "title": title, "parent_id": client.ids["Jane Doe"]}).json()["id"]  # type: ignore[attr-defined]


def merge_args(client: TestClient) -> dict:
    alias = skill(client, "Py")
    return {"canonical_id": client.ids["Python"], "alias_ids": [alias]}  # type: ignore[attr-defined]


def source(client: TestClient) -> str:
    return client.get("/api/sources").json()[0]["source"]


def test_a_merge_card_lists_the_facts_and_changes_nothing_until_approved(career: TestClient) -> None:
    args = merge_args(career)
    career.script(("merge_facts", args), "unused")  # type: ignore[attr-defined]
    before = state(career)
    events = chat(career, "Merge Py into Python")
    [interrupt] = events[-1]["outcome"]["interrupts"]
    assert interrupt["message"] == "Merge into Skill 'Python' (kept):\n- 'Py'\nThey are shown as 'Python' from now on. This can be undone."
    assert state(career) == before and merges(career) == []


def test_an_approved_merge_shows_in_list_merges_and_an_approved_undo_removes_it(career: TestClient) -> None:
    args = merge_args(career)
    assert results(answer(career, "merge_facts", args, APPROVED)) == ["Changed: Merge into Skill 'Python' (kept):\n- 'Py'\nThey are shown as 'Python' from now on. This can be undone."]
    assert "Py" not in {f["title"] for f in career.get("/api/facts").json()} and merges(career) == [("Py", "Python")]
    undo = {"alias_id": args["alias_ids"][0], "canonical_id": args["canonical_id"]}
    assert results(answer(career, "unmerge_fact", undo, APPROVED)) == ["Changed: Show 'Py' separately from 'Python' again"]
    assert "Py" in {f["title"] for f in career.get("/api/facts").json()} and merges(career) == []


def test_several_facts_merge_into_one(career: TestClient) -> None:
    ids = [skill(career, t) for t in ("Py", "Pyton")]
    answer(career, "merge_facts", {"canonical_id": career.ids["Python"], "alias_ids": ids}, APPROVED)  # type: ignore[attr-defined]
    assert merges(career) == [("Py", "Python"), ("Pyton", "Python")]


def test_a_relationship_is_added_and_removed_through_the_graph(career: TestClient) -> None:
    link = {"source_id": career.ids["Senior Engineer"], "target_id": skill(career, "Terraform"), "kind": "USES_SKILL"}  # type: ignore[attr-defined]
    assert results(answer(career, "add_relationship", link, APPROVED)) == ["Changed: Link Position 'Senior Engineer' and Skill 'Terraform' (USES_SKILL)"]
    assert ("Senior Engineer", "Terraform", "USES_SKILL") in edges(career)
    assert results(answer(career, "remove_relationship", link, APPROVED)) == ["Changed: Unlink Position 'Senior Engineer' and Skill 'Terraform' (USES_SKILL)"]
    assert ("Senior Engineer", "Terraform", "USES_SKILL") not in edges(career)


def test_a_source_is_removed_and_the_card_says_how_many_facts_it_hides(career: TestClient) -> None:
    name = source(career)
    count = career.get("/api/sources").json()[0]["facts"]
    career.script(("remove_source", {"source": name}), "unused")  # type: ignore[attr-defined]
    [interrupt] = chat(career)[-1]["outcome"]["interrupts"]
    assert interrupt["message"] == f"Remove source '{name}'. Its {count} facts are hidden unless another source states them."
    assert any(s["source"] == name for s in career.get("/api/sources").json())
    answer(career, "remove_source", {"source": name}, APPROVED)
    assert not any(s["source"] == name for s in career.get("/api/sources").json())


def declined(client: TestClient) -> list[tuple[str, dict]]:
    args = merge_args(client)
    link = {"source_id": client.ids["Senior Engineer"], "target_id": client.ids["Cut build times by 60%"], "kind": "ACHIEVED"}  # type: ignore[attr-defined]
    return [("merge_facts", args), ("add_relationship", {**link, "kind": "USES_SKILL", "target_id": client.ids["Python"]}),  # type: ignore[attr-defined]
            ("remove_relationship", link), ("remove_source", {"source": source(client)})]


@pytest.mark.parametrize("index", range(4), ids=["merge", "add link", "remove link", "remove source"])
def test_a_declined_write_changes_nothing(career: TestClient, index: int) -> None:
    name, args = declined(career)[index]
    before = state(career)
    events = answer(career, name, args, [{"interruptId": "c1", "status": "resolved", "payload": {"approved": False}}])
    assert results(events) == ["Declined by the user."] and state(career) == before


def test_a_declined_undo_keeps_the_merge(career: TestClient) -> None:
    args = merge_args(career)
    answer(career, "merge_facts", args, APPROVED)
    undo = {"alias_id": args["alias_ids"][0], "canonical_id": args["canonical_id"]}
    assert results(answer(career, "unmerge_fact", undo, [{"interruptId": "c1", "status": "cancelled"}])) == ["Declined by the user."]
    assert merges(career) == [("Py", "Python")]


def refused(client: TestClient) -> list[tuple[str, dict]]:
    ids = client.ids  # type: ignore[attr-defined]
    return [("merge_facts", {"canonical_id": ids["Python"], "alias_ids": [ids["Senior Engineer"]]}),  # another kind
            ("merge_facts", {"canonical_id": ids["Python"], "alias_ids": [ids["Python"]]}),  # itself
            ("merge_facts", {"canonical_id": ids["Python"], "alias_ids": ["nope"]}),
            ("merge_facts", {"canonical_id": ids["Python"], "alias_ids": []}),
            ("unmerge_fact", {"alias_id": ids["Python"], "canonical_id": ids["Kubernetes"]}),  # never merged
            ("add_relationship", {"source_id": ids["Cut build times by 60%"], "target_id": ids["Python"], "kind": "AT"}),  # wrong kinds
            ("add_relationship", {"source_id": ids["Senior Engineer"], "target_id": ids["Cut build times by 60%"], "kind": "ACHIEVED"}),  # already there
            ("remove_relationship", {"source_id": ids["Senior Engineer"], "target_id": ids["Python"], "kind": "USES_SKILL"}),  # not there
            ("add_relationship", {"source_id": ids["Senior Engineer"], "target_id": ids["Python"], "kind": "HAS_SKILL"}),  # not an editable kind
            ("remove_source", {"source": "nothing.pdf"})]


@pytest.mark.parametrize("index", range(10))
def test_a_refused_write_answers_with_the_reason_and_shows_no_card(career: TestClient, index: int) -> None:
    name, args = refused(career)[index]
    career.script((name, args), "Sorry.")  # type: ignore[attr-defined]
    before = state(career)
    events = chat(career)
    assert results(events)[0].startswith("Failed:") and text(events) == "Sorry." and events[-1].get("outcome") is None
    assert state(career) == before
