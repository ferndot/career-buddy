"""Blackbox tests through the HTTP front door: import, then read documents back."""

from pathlib import Path

from fastapi.testclient import TestClient

from career_buddy.web.app import create_app

JANE_TEXT = """Jane Doe
Experience
Senior Engineer at Acme Corp, Mar 2019 - Jan 2023
- Cut build times by 60%
- Migrated 40 services to Kubernetes
Engineer at Globex, Jun 2016 - Feb 2019
- Built ETL jobs

Skills
Python, Kubernetes

Education
University of Lisbon
"""


def seed_jane(client: TestClient) -> None:
    """Imports the text, then fills what the offline reader does not read: headline, summary and the degree."""
    assert client.post("/api/import/text", json={"text": JANE_TEXT}).status_code == 200
    facts = {f["kind"]: f["id"] for f in client.get("/api/facts").json() if f["kind"] in ("Person", "Education")}
    summary = {"headline": "Platform engineer", "summary": "Builds reliable data pipelines", "location": "Lisbon, Portugal"}
    degree = {"school": "University of Lisbon", "started": "2012", "finished": "2016"}
    assert client.patch(f"/api/facts/{facts['Person']}", json={"attributes": summary}).status_code == 200
    assert client.patch(f"/api/facts/{facts['Education']}", json={"title": "BSc Computer Science", "attributes": degree}).status_code == 200


RESUME_TEXT = """Ada Lovelace

Experience
Analyst at Analytical Society, 2010 - 2015
- Wrote the first published algorithm
Skills
Mathematics, Python

Education
Trinity College
"""


def test_import_then_resume_and_letter(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        seed_jane(client)

        md = client.get("/api/resume/markdown").text
        assert md.startswith("# Jane Doe")
        assert "### Senior Engineer, Acme Corp" in md
        assert "- Cut build times by 60%" in md
        assert "- BSc Computer Science, University of Lisbon" in md

        html = client.get("/api/resume/html")
        assert html.headers["content-type"].startswith("text/html")
        assert "Cut build times by 60%" in html.text

        letter = client.post("/api/cover-letter", json={"job_text": "We need Kubernetes and build speed experts"})
        assert "Senior Engineer at Acme Corp" in letter.text
        assert "Kubernetes" in letter.text


def test_repeated_import_is_idempotent(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        seed_jane(client)
        seed_jane(client)
        positions = [f for f in client.get("/api/facts", params={"kind": "Position"}).json()]
        assert len(positions) == 2


def test_text_import_and_restart_replays_log(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/import/text", json={"text": RESUME_TEXT}).status_code == 200

    # A fresh app over the same data dir rebuilds the graph from the event log.
    with TestClient(create_app(tmp_path)) as client:
        md = client.get("/api/resume/markdown").text
        assert md.startswith("# Ada Lovelace")
        assert "### Analyst, Analytical Society (2010 – 2015)" in md
        assert "- Wrote the first published algorithm" in md
        assert "## Skills\nMathematics, Python" in md
        assert "Trinity College, Trinity College" not in md


def test_empty_text_is_rejected(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/import/text", json={"text": "   "}).status_code == 400
