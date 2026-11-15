"""POST /api/import/file: the three error codes and the plain-text happy path."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_graph.web.app import create_app
from layouts import IMAGE_ONLY, TWO_COLUMNS, pdf

TEXT = b"Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first algorithm\n"
MB10 = 10 * 1024 * 1024


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def upload(client: TestClient, name: str, data: bytes):
    return client.post("/api/import/file", files={"file": (name, data, "application/octet-stream")})


@pytest.mark.parametrize("name", ["resume.txt", "resume.MD"])
def test_text_and_markdown_files_import_like_pasted_text(client, name) -> None:
    assert upload(client, name, TEXT).json() == {"facts": 4}
    titles = [f["title"] for f in client.get("/api/facts", params={"kind": "Position"}).json()]
    assert titles == ["Analyst"]


def test_oversized_upload_is_413(client) -> None:
    assert upload(client, "resume.txt", b"x" * (MB10 + 1)).status_code == 413


def test_exactly_10_mb_is_accepted(client) -> None:
    assert upload(client, "resume.txt", b"Ada\n" + b" " * (MB10 - 4)).status_code == 200


@pytest.mark.parametrize("name", ["resume.rtf", "resume.png", "resume", "resume.doc"])
def test_unknown_file_type_is_415(client, name) -> None:
    assert upload(client, name, TEXT).status_code == 415


def test_corrupt_pdf_is_422(client) -> None:
    res = upload(client, "resume.pdf", b"%PDF-1.4 this is not really a pdf")
    assert res.status_code == 422 and "PDF" in res.json()["detail"]


def test_truncated_pdf_is_422(client, chromium) -> None:
    assert upload(client, "resume.pdf", pdf(TWO_COLUMNS)[:300]).status_code == 422


def test_corrupt_docx_is_422(client) -> None:
    assert upload(client, "resume.docx", b"not a zip").status_code == 422


def test_zip_that_is_not_a_docx_is_422(client) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("hello.txt", "hi")
    assert upload(client, "resume.docx", buf.getvalue()).status_code == 422


def test_scanned_pdf_without_a_text_layer_is_422(client, chromium) -> None:
    res = upload(client, "scan.pdf", pdf(IMAGE_ONLY))
    assert res.status_code == 422
    assert res.json()["detail"] == "No text layer; OCR is not supported"


def test_empty_text_file_is_422(client) -> None:
    assert upload(client, "resume.txt", b"  \n ").status_code == 422
