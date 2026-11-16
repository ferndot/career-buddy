"""Dates of positions and education through HTTP: stored as partial ISO dates, and validated."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app

TEXT = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, Mar 2010 - 2015\n- Wrote the first published algorithm\n"


def attributes(client: TestClient, kind: str, title: str) -> dict:
    return next(f["attributes"] for f in client.get("/api/facts", params={"kind": kind}).json() if f["title"] == title)


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def test_a_position_added_by_hand_keeps_its_dates_at_the_precision_given(client) -> None:
    client.post("/api/import/text", json={"text": TEXT})
    person = client.get("/api/profile").json()["id"]
    res = client.post("/api/facts", json={"kind": "Position", "title": "Consultant", "parent_id": person,
                                          "attributes": {"organization": "Initech", "started": "2021-03-14", "finished": "present"}})
    assert res.status_code == 201
    assert attributes(client, "Position", "Consultant") == {"started": "2021-03-14", "finished": "present"}
    assert "### Consultant, Initech (14 Mar 2021 – Present)" in client.get("/api/resume/markdown").text


@pytest.mark.parametrize("bad", [{"started": "March 2021"}, {"finished": "2021-13"}, {"started": "2022", "finished": "2021"}, {"started": "present"}])
def test_invalid_dates_are_rejected_on_add_and_on_edit(client, bad: dict) -> None:
    client.post("/api/import/text", json={"text": TEXT})
    person = client.get("/api/profile").json()["id"]
    assert client.post("/api/facts", json={"kind": "Position", "title": "X", "parent_id": person, "attributes": bad}).status_code == 422
    position = next(f["id"] for f in client.get("/api/facts", params={"kind": "Position"}).json())
    assert client.patch(f"/api/facts/{position}", json={"attributes": bad}).status_code == 422


def test_an_edit_clears_a_date_and_a_year_end_may_follow_a_month_start(client) -> None:
    client.post("/api/import/text", json={"text": TEXT})
    position = next(f["id"] for f in client.get("/api/facts", params={"kind": "Position"}).json())
    res = client.patch(f"/api/facts/{position}", json={"attributes": {"started": "2010-03", "finished": ""}})
    assert res.json()["attributes"] == {"started": "2010-03"}
    assert client.patch(f"/api/facts/{position}", json={"attributes": {"started": "2010-06", "finished": "2010"}}).status_code == 200


def test_imported_period_text_is_stored_as_dates(client) -> None:
    client.post("/api/import/text", json={"text": TEXT})
    assert attributes(client, "Position", "Analyst") == {"started": "2010-03", "finished": "2015"}
    assert "### Analyst, Analytical Society (Mar 2010 – 2015)" in client.get("/api/resume/markdown").text
