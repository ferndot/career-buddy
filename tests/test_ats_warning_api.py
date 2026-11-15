"""A failing ATS check is a warning: the file still downloads and the issues travel with it."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_graph.adapters.outputs.render_text import TextRenderer
from career_graph.domain.document import Document, Style
from career_graph.web.app import create_app
from test_api import linkedin_zip


class DropsBullets(TextRenderer):
    """A deliberately broken renderer: bullets never reach the file, so the read-back misses lines."""

    def render(self, doc: Document, style: Style) -> bytes:
        return super().render(Document(doc.name, doc.intro, ()), style)


@pytest.fixture
def broken(tmp_path: Path):
    with TestClient(create_app(tmp_path, renderers=[DropsBullets()])) as client:
        client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
        yield client


BODY = {"template": "resume-classic", "format": "txt"}


def test_a_failing_check_still_downloads_the_file_with_the_issues_in_a_header(broken: TestClient) -> None:
    res = broken.post("/api/documents/render", json=BODY)
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.txt"'
    assert res.text.startswith("Jane Doe\n") and "Cut build times" not in res.text
    assert set(res.headers["x-ats-issues"].split(",")) >= {"coverage", "headings"}


def test_the_json_preview_carries_the_same_issues(broken: TestClient) -> None:
    ats = broken.post("/api/documents/preview", json=BODY).json()["ats"]
    assert ats["format"] == "txt" and ats["passes"] is False
    assert {i["code"] for i in ats["issues"]} >= {"coverage", "headings"}
    assert all(i["message"] for i in ats["issues"])


def test_the_preview_checks_docx_by_default_and_passes_for_a_sound_renderer(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
        ats = client.post("/api/documents/preview", json={"template": "resume-classic"}).json()["ats"]
    assert ats == {"format": "docx", "passes": True, "issues": []}
