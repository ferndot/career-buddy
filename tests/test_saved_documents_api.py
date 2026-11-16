"""Saved documents over HTTP: saved once as html, downloaded in any format. Skill / education selection in rendered documents."""

import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.adapters.readers.docx_text import DocxTextReader
from career_buddy.web.app import create_app
from test_api import seed_jane

BODY = {"template": "resume-classic"}
LETTER = {"template": "cover-letter", "inputs": {"company": "Acme", "role": "Engineer"}}
LEGACY_ID = "a" * 32


def open_client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path))
    client.__enter__()
    return client


@pytest.fixture
def client(tmp_path: Path):
    c = open_client(tmp_path)
    seed_jane(c)
    yield c
    c.__exit__(None, None, None)


def save(client: TestClient, **extra):
    return client.post("/api/saved-documents", json={**BODY, **extra})


def file(client: TestClient, record: dict, fmt: str | None = None):
    return client.get(f"/api/saved-documents/{record['id']}/file", params={"format": fmt} if fmt else {})


def render(client: TestClient, fmt: str, **extra):
    return client.post("/api/documents/render", json={**BODY, "format": fmt, **extra})


def plant_legacy(tmp_path: Path, fmt: str = "markdown", ext: str = "md", media_type: str = "text/markdown") -> str:
    """A document saved before html storage: one rendered file and a meta.json with no `version`."""
    folder = tmp_path / "objects" / "documents" / LEGACY_ID
    folder.mkdir(parents=True)
    (folder / f"file.{ext}").write_bytes(b"# Jane Doe\n")
    (folder / "meta.json").write_text(json.dumps({
        "id": LEGACY_ID, "label": "Old one", "template": "resume-classic", "format": fmt, "filename": f"Jane-Doe-Resume.{ext}",
        "media_type": media_type, "created_at": "2020-01-01T00:00:00+00:00", "ats_issues": []}))
    return LEGACY_ID


def test_saving_returns_a_record_and_keeps_the_document_as_html_and_css(client: TestClient) -> None:
    res = save(client, label="For Acme", font="serif")
    assert res.status_code == 201
    record = res.json()
    assert set(record) == {"id", "label", "template", "format", "filename", "created_at", "ats_issues", "version"}
    assert record["label"] == "For Acme" and record["filename"] == "Jane-Doe-Resume" and record["version"] == 2
    assert record["format"] == "" and len(record["id"]) == 32

    content = client.get(f"/api/saved-documents/{record['id']}/content").json()
    assert content["overrides"] == {} and "Times New Roman" in content["css"]
    html = content["html"]
    assert re.search(r'<h1 data-slot="s1" data-fact-id="[0-9a-f-]+" data-field="text" data-origin="fact">Jane Doe</h1>', html)
    assert re.search(r'<li data-slot="s\d+" data-fact-id="[0-9a-f-]+" data-field="text" data-origin="fact">Cut build times by 60%</li>', html)
    assert "<script" not in html and "<h2 data-origin=\"boilerplate\">Experience</h2>" in html


def test_an_empty_label_falls_back_to_the_file_name_without_extension(client: TestClient) -> None:
    assert save(client).json()["label"] == "Jane-Doe-Resume"
    assert save(client, label="   ").json()["label"] == "Jane-Doe-Resume"


def test_a_stale_client_that_still_sends_a_format_is_not_an_error(client: TestClient) -> None:
    assert save(client, format="pdf").status_code == 201


def test_docx_is_the_default_download_and_has_the_saved_content(client: TestClient) -> None:
    record = save(client).json()
    res = file(client, record)
    assert res.status_code == 200 and res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.docx"'
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert file(client, record, "docx").content == res.content
    assert DocxTextReader().read(res.content).lines == DocxTextReader().read(render(client, "docx").content).lines


def test_txt_download_matches_what_the_render_route_prints(client: TestClient) -> None:
    res = file(client, save(client).json(), "txt")
    assert res.status_code == 200 and res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.txt"'
    assert res.headers["content-type"].startswith("text/plain")
    assert res.content == render(client, "txt").content and b"- Cut build times by 60%" in res.content


def test_a_cover_letter_keeps_its_untitled_body_apart_from_the_contact_lines(client: TestClient) -> None:
    record = client.post("/api/saved-documents", json=LETTER).json()
    assert file(client, record, "txt").content == client.post("/api/documents/render", json={**LETTER, "format": "txt"}).content


def test_pdf_download_is_converted_from_the_saved_html(client: TestClient, chromium) -> None:
    res = file(client, save(client).json(), "pdf")
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    assert res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.pdf"'


def test_an_unknown_download_format_is_422(client: TestClient) -> None:
    assert file(client, save(client).json(), "markdown").status_code == 422


def test_the_ats_check_runs_on_download_and_the_record_keeps_the_save_time_result(client: TestClient) -> None:
    record = save(client).json()
    expected = [c for c in render(client, "docx").headers.get("x-ats-issues", "").split(",") if c]
    assert record["ats_issues"] == expected
    assert file(client, record, "txt").headers.get("x-ats-issues", "") == render(client, "txt").headers.get("x-ats-issues", "")


def test_overrides_on_disk_win_over_the_stored_text_at_download(client: TestClient, tmp_path: Path) -> None:
    """overrides.json is read at download time. Nothing writes it yet, so the test plants one in the stored layout."""
    record = save(client).json()
    assert b"Jane Doe" in file(client, record, "txt").content
    (tmp_path / "objects" / "documents" / record["id"] / "overrides.json").write_text(json.dumps({"s1": "Jane Q. Doe"}))
    out = file(client, record, "txt").content
    assert out.startswith(b"Jane Q. Doe\n") and b"Jane Doe" not in out
    assert client.get(f"/api/saved-documents/{record['id']}/content").json()["overrides"] == {"s1": "Jane Q. Doe"}


def test_the_list_is_newest_first_and_survives_a_restart(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        seed_jane(client)
        first = save(client, label="first").json()
        time.sleep(0.01)
        second = save(client, label="second").json()
        assert [r["id"] for r in client.get("/api/saved-documents").json()] == [second["id"], first["id"]]
    with open_client(tmp_path) as again:
        listed = again.get("/api/saved-documents").json()
        assert [r["label"] for r in listed] == ["second", "first"]
        assert again.get(f"/api/saved-documents/{first['id']}/file", params={"format": "txt"}).content.startswith(b"Jane Doe")


def test_the_list_is_empty_before_anything_is_saved(client: TestClient) -> None:
    assert client.get("/api/saved-documents").json() == []


def test_deleting_removes_the_record_and_every_file(client: TestClient, tmp_path: Path) -> None:
    keep, gone = save(client, label="keep").json(), save(client, label="gone").json()
    assert client.delete(f"/api/saved-documents/{gone['id']}").status_code == 204
    assert [r["id"] for r in client.get("/api/saved-documents").json()] == [keep["id"]]
    assert file(client, gone).status_code == 404 and client.get(f"/api/saved-documents/{gone['id']}/content").status_code == 404
    assert client.delete(f"/api/saved-documents/{gone['id']}").status_code == 404
    assert file(client, keep).status_code == 200
    assert not [p for p in (tmp_path / "objects" / "documents" / gone["id"]).rglob("*") if p.is_file()]


@pytest.mark.parametrize("doc_id", ["0" * 32, "abc", "A" * 32, "..", "..%2F..%2Fevents.jsonl", "0" * 31 + "g"])
def test_unknown_or_malformed_ids_are_404(client: TestClient, doc_id: str) -> None:
    for tail in ("/file", "/content"):
        assert client.get(f"/api/saved-documents/{doc_id}{tail}").status_code == 404
    assert client.delete(f"/api/saved-documents/{doc_id}").status_code == 404


def test_an_unknown_template_is_404_and_nothing_is_stored(client: TestClient) -> None:
    assert save(client, template="nope").status_code == 404
    assert client.get("/api/saved-documents").json() == []


def test_missing_inputs_for_a_letter_are_422(client: TestClient) -> None:
    assert client.post("/api/saved-documents", json={"template": "cover-letter"}).status_code == 422


def test_a_legacy_document_is_listed_and_downloads_in_its_own_format(client: TestClient, tmp_path: Path) -> None:
    doc_id = plant_legacy(tmp_path)  # meta.json has no `version`, `font` or `paper`
    (old,) = client.get("/api/saved-documents").json()
    assert old["id"] == doc_id and old["version"] == 1 and old["format"] == "markdown" and old["filename"] == "Jane-Doe-Resume.md"
    res = client.get(f"/api/saved-documents/{doc_id}/file")
    assert res.content == b"# Jane Doe\n" and res.headers["content-type"].startswith("text/markdown")
    assert res.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.md"'
    assert client.delete(f"/api/saved-documents/{doc_id}").status_code == 204


def test_a_legacy_document_has_no_content_and_no_other_format(client: TestClient, tmp_path: Path) -> None:
    doc_id = plant_legacy(tmp_path, "docx", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert client.get(f"/api/saved-documents/{doc_id}/content").status_code == 409
    assert client.get(f"/api/saved-documents/{doc_id}/file", params={"format": "txt"}).status_code == 409
    assert client.get(f"/api/saved-documents/{doc_id}/file", params={"format": "docx"}).status_code == 200


def skill_ids(client: TestClient) -> dict[str, str]:
    profile = client.get("/api/profile").json()
    return dict(zip(profile["skills"], profile["skill_ids"]))


def render_text(client: TestClient, **extra) -> str:
    return render(client, "markdown", **extra).text


def test_a_skill_selection_decides_which_skills_are_printed(client: TestClient) -> None:
    ids = skill_ids(client)
    assert {"Python", "Kubernetes"} <= ids.keys()
    assert "Python" in render_text(client) and "Kubernetes" in render_text(client)
    only = render_text(client, skill_ids=[ids["Kubernetes"]])
    assert "Kubernetes" in only and "Python" not in only.split("Skills")[-1]
    assert "Skills" not in render_text(client, skill_ids=[])


def test_an_education_selection_decides_which_entries_are_printed(client: TestClient) -> None:
    education = client.get("/api/profile").json()["education"]
    assert education and "University of Lisbon" in render_text(client)
    assert "University of Lisbon" not in render_text(client, education_ids=[])
    assert "University of Lisbon" in render_text(client, education_ids=[education[0]["id"]])


def test_selections_reach_saved_documents_too(client: TestClient) -> None:
    record = save(client, skill_ids=[skill_ids(client)["Kubernetes"]], education_ids=[]).json()
    saved = file(client, record, "txt").text
    assert "University of Lisbon" not in saved and "Python" not in saved.split("Skills")[-1]


def test_preview_honours_the_same_selection(client: TestClient) -> None:
    res = client.post("/api/documents/preview", json={"template": "resume-classic", "education_ids": [], "skill_ids": []})
    assert res.status_code == 200
    text = "\n".join(res.json()["lines"])
    assert "University of Lisbon" not in text
