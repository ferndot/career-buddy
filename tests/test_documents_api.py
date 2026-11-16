"""HTTP front door for documents: render and ATS-check resume-classic in every format."""

import io
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from test_api import seed_jane

FORMATS = ["markdown", "html", "txt", "docx", "pdf"]


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as client:
        seed_jane(client)
        yield client


def render(client: TestClient, fmt: str, **extra: str):
    return client.post("/api/documents/render", json={"template": "resume-classic", "format": fmt, **extra})


def test_render_text_formats(client: TestClient) -> None:
    md = render(client, "markdown")
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.md"'
    assert md.text.startswith("# Jane Doe") and "- Cut build times by 60%" in md.text
    assert "<h1>Jane Doe</h1>" in render(client, "html").text
    assert render(client, "txt").text.startswith("Jane Doe\n")


def test_render_docx_download_opens_in_word_format(client: TestClient) -> None:
    res = render(client, "docx")
    assert res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.docx"'
    texts = [p.text for p in DocxDocument(io.BytesIO(res.content)).paragraphs]
    assert texts[0] == "Jane Doe" and "Cut build times by 60%" in texts


def test_render_pdf_download(client: TestClient, chromium) -> None:
    res = render(client, "pdf", paper="a4")
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.pdf"'
    assert res.content.startswith(b"%PDF")


@pytest.mark.parametrize("fmt", FORMATS)
def test_ats_check_passes_for_resume_classic_in_every_format(client: TestClient, chromium, fmt: str) -> None:
    res = client.post("/api/documents/check", json={"template": "resume-classic", "format": fmt})
    assert res.status_code == 200
    assert res.json() == {"passes": True, "issues": []}


def test_old_resume_endpoint_matches_the_new_markdown(client: TestClient) -> None:
    assert client.get("/api/resume/markdown").text == render(client, "markdown").text


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        ({"template": "resume-nope", "format": "docx"}, 404, "Unknown template"),
        ({"template": "resume-classic", "format": "rtf"}, 404, "Unknown format"),
        ({"template": "resume-classic", "format": "docx", "paper": "legal"}, 422, "paper"),
    ],
)
def test_bad_requests(client: TestClient, body: dict, status: int, detail: str) -> None:
    res = client.post("/api/documents/render", json=body)
    assert res.status_code == status and detail in res.text


def test_pdf_without_chromium_is_503_with_the_install_step(client: TestClient, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "no-browsers"))
    res = render(client, "pdf")
    assert res.status_code == 503
    assert "playwright install chromium" in res.json()["detail"]
