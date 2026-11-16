"""Users add and remove links between facts. The change is logged, so it survives a restart and a re-import."""

from fastapi.testclient import TestClient

from career_buddy.web.app import create_app

TEXT = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first published algorithm\n"


def _setup(client: TestClient) -> tuple[str, str, dict[str, str]]:
    """A position, a second organization (from a hand-made position), and the AT link between them as the API shows edges."""
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    position = next(f["id"] for f in client.get("/api/facts").json() if f["kind"] == "Position")
    person = next(f["id"] for f in client.get("/api/facts").json() if f["kind"] == "Person")
    other = {"kind": "Position", "title": "Fellow", "parent_id": person, "attributes": {"organization": "Royal Society"}}
    client.post("/api/facts", json=other)  # a hand-made position brings its organization with it
    org = next(f["id"] for f in client.get("/api/facts").json() if f["title"] == "Royal Society")
    return position, org, {"source_id": position, "target_id": org, "kind": "AT"}


def _has_edge(client: TestClient, link: dict[str, str]) -> bool:
    edges = client.get("/api/graph").json()["edges"]
    return {"source": link["source_id"], "target": link["target_id"], "kind": link["kind"]} in edges


def test_an_added_link_shows_in_the_graph(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        _, _, link = _setup(client)
        assert not _has_edge(client, link)
        response = client.post("/api/links", json=link)
        assert response.status_code == 201 and response.json() == {}
        assert _has_edge(client, link)
        assert client.post("/api/links", json=link).status_code == 201  # adding it again changes nothing
        assert client.get("/api/graph").json()["edges"].count(
            {"source": link["source_id"], "target": link["target_id"], "kind": "AT"}) == 1


def test_a_removed_link_is_hidden_and_can_come_back(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        _, _, link = _setup(client)
        client.post("/api/links", json=link)
        assert client.delete("/api/links", params=link).status_code == 204
        assert not _has_edge(client, link)
        assert client.delete("/api/links", params=link).status_code == 404  # nothing left to remove
        client.post("/api/links", json=link)
        assert _has_edge(client, link)


def test_an_imported_link_stays_removed_after_a_re_import(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, _, _ = _setup(client)
        edge = next(e for e in client.get("/api/graph").json()["edges"] if e["kind"] == "AT" and e["source"] == position)
        link = {"source_id": edge["source"], "target_id": edge["target"], "kind": "AT"}
        assert client.delete("/api/links", params=link).status_code == 204
        client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
        assert not _has_edge(client, link)


def test_a_link_between_the_wrong_kinds_is_rejected(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, org, link = _setup(client)
        assert client.post("/api/links", json={**link, "source_id": org, "target_id": position}).status_code == 422
        assert client.post("/api/links", json={**link, "kind": "HAS_SKILL"}).status_code == 422
        assert client.post("/api/links", json={**link, "target_id": "nope"}).status_code == 404
        assert not _has_edge(client, link)


def test_link_changes_survive_a_reload_of_the_event_log(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, _, link = _setup(client)
        client.post("/api/links", json=link)
        imported = next(e for e in client.get("/api/graph").json()["edges"]
                        if e["kind"] == "AT" and e["source"] == position and e["target"] != link["target_id"])
        gone = {"source_id": position, "target_id": imported["target"], "kind": "AT"}
        client.delete("/api/links", params=gone)
    with TestClient(create_app(tmp_path)) as reloaded:
        assert _has_edge(reloaded, link)
        assert not _has_edge(reloaded, gone)


def test_an_achievement_can_use_a_skill_but_not_the_other_way_round(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, _, _ = _setup(client)
        person = next(f["id"] for f in client.get("/api/facts").json() if f["kind"] == "Person")
        skill = client.post("/api/facts", json={"kind": "Skill", "title": "Mathematics", "parent_id": person}).json()["id"]
        achievement = next(f["id"] for f in client.get("/api/facts").json() if f["kind"] == "Achievement")
        link = {"source_id": achievement, "target_id": skill, "kind": "USES_SKILL"}
        assert client.post("/api/links", json=link).status_code == 201
        assert _has_edge(client, link)
        reverse = {"source_id": skill, "target_id": achievement, "kind": "USES_SKILL"}
        assert client.post("/api/links", json=reverse).status_code == 422
        assert not _has_edge(client, reverse)
        position_link = {"source_id": position, "target_id": skill, "kind": "USES_SKILL"}  # the position rule still holds
        assert client.post("/api/links", json=position_link).status_code == 201
