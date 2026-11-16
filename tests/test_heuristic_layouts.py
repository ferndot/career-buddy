"""The offline extractor on real resume layouts, driven through POST /api/import/text."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def import_text(client: TestClient, text: str) -> dict[str, list[dict]]:
    assert client.post("/api/import/text", json={"text": text}).status_code == 200
    by_kind: dict[str, list[dict]] = {}
    for fact in client.get("/api/facts").json():
        by_kind.setdefault(fact["kind"], []).append(fact)
    return by_kind


def test_every_bullet_glyph_starts_an_achievement(client) -> None:
    text = "Ada\nExperience\nAnalyst at Society, 2010 - 2015\n● one\n▪ two\n■ three\n◦ four\n- five\n• six\n* seven\n"
    found = import_text(client, text)
    assert [f["title"] for f in found["Achievement"]] == ["one", "two", "three", "four", "five", "six", "seven"]


def test_glyph_bullets_in_a_skills_list_are_stripped(client) -> None:
    found = import_text(client, "Ada\nSkills\n● Python, ▪ Go\n")
    assert [f["title"] for f in found["Skill"]] == ["Python", "Go"]


STACKED = """Ada Lovelace
EXPERIENCE
Analytical Society
Lead Analyst
Mar 2012 – Present
● Wrote the first algorithm
Babbage & Co
Analyst
2010 - 2012
▪ Checked the tables
"""


def test_org_title_dates_on_separate_lines(client) -> None:
    found = import_text(client, STACKED)
    assert [(f["title"], f["attributes"]) for f in found["Position"]] == [
        ("Lead Analyst", {"period": "Mar 2012 – Present"}),
        ("Analyst", {"period": "2010 - 2012"}),
    ]
    assert [f["title"] for f in found["Organization"]] == ["Analytical Society", "Babbage & Co"]
    assert [f["title"] for f in found["Achievement"]] == ["Wrote the first algorithm", "Checked the tables"]


def test_contact_lines_are_attributes_not_the_name(client) -> None:
    text = "ada@example.com | +44 20 7946 0958\nAda Lovelace\nExperience\nAnalyst at Society, 2010 - 2015\n"
    (person,) = import_text(client, text)["Person"]
    assert person["title"] == "Ada Lovelace"
    assert person["attributes"] == {"email": "ada@example.com", "phone": "+44 20 7946 0958"}


def test_a_year_range_is_not_mistaken_for_a_phone_number(client) -> None:
    (person,) = import_text(client, "Ada Lovelace\n2010 - 2015\nExperience\nAnalyst at Society, 2010 - 2015\n")["Person"]
    assert person["title"] == "Ada Lovelace" and person["attributes"] == {}
