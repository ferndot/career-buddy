"""Deleting a fact is permanent: its achievements and edges go too, and it stays gone after a restart."""

from fastapi.testclient import TestClient

from career_buddy.web.app import create_app

TEXT = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first published algorithm\n"


def _imported(client: TestClient) -> tuple[str, str]:
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    facts = client.get("/api/facts").json()
    kinds = {f["kind"]: f["id"] for f in facts}
    return kinds["Position"], kinds["Achievement"]


def test_deleting_a_position_removes_it_and_its_achievements(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, achievement = _imported(client)
        assert client.delete(f"/api/facts/{position}").status_code == 204
        ids = {f["id"] for f in client.get("/api/facts").json()}
        assert position not in ids and achievement not in ids
        graph = client.get("/api/graph").json()
        assert not {position, achievement} & {n["id"] for n in graph["nodes"]}


def test_deleting_an_unknown_fact_is_404(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        assert client.delete("/api/facts/nope").status_code == 404


def test_deletion_survives_a_reload_of_the_event_log(tmp_path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        position, achievement = _imported(client)
        client.delete(f"/api/facts/{position}")
    with TestClient(create_app(tmp_path)) as reloaded:
        ids = {f["id"] for f in reloaded.get("/api/facts").json()}
        assert position not in ids and achievement not in ids
        assert reloaded.delete(f"/api/facts/{position}").status_code == 404
