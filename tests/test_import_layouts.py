"""Real resume layouts through /api/import/file: two-column PDFs, and DOCX tables, text boxes and headers."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_graph.web.app import create_app
from layouts import TWO_COLUMNS, pdf, resume_docx


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def facts(client: TestClient, *kinds: str) -> list[dict]:
    return [f for f in client.get("/api/facts").json() if f["kind"] in kinds]


def import_docx(client: TestClient):
    return client.post("/api/import/file", files={"file": ("cv.docx", resume_docx(), "application/octet-stream")})


def test_two_column_pdf_facts_are_in_reading_order(client, chromium) -> None:
    res = client.post("/api/import/file", files={"file": ("cv.pdf", pdf(TWO_COLUMNS), "application/pdf")})
    assert res.status_code == 200
    assert [f["title"] for f in facts(client, "Position", "Achievement")] == [
        "Senior Engineer", "Cut build times by 60%", "Led a team of 8 engineers",
        "Engineer", "Built the billing pipeline", "Mentored 5 interns",
    ]
    assert {f["title"] for f in facts(client, "Skill")} == {"Python", "Go"}


def test_docx_table_text_box_and_header_are_imported(client) -> None:
    assert import_docx(client).status_code == 200
    (person,) = facts(client, "Person")
    assert person["title"] == "Jane Doe"
    assert person["attributes"] == {"email": "jane@example.com", "phone": "+351 912 345 678"}  # from the header
    assert {f["title"] for f in facts(client, "Skill")} == {"Python", "Go", "SQL"}  # from the table
    assert [f["title"] for f in facts(client, "Education")] == ["University of Lisbon"]  # from the text box


def test_docx_stacked_org_title_dates_becomes_a_position(client) -> None:
    import_docx(client)
    (position,) = facts(client, "Position")
    assert position["title"] == "Senior Engineer"
    assert position["attributes"] == {"period": "Mar 2019 - Present"}
    assert {f["title"] for f in facts(client, "Organization")} == {"Acme Corp", "University of Lisbon"}
    assert [f["title"] for f in facts(client, "Achievement")] == ["Cut build times by 60%"]
