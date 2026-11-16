"""Saved documents over HTTP, and skill / education selection in rendered documents."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.adapters.outputs.render_text import TextRenderer
from career_buddy.application.ports import RendererUnavailable
from career_buddy.domain.document import Document, Style
from career_buddy.web.app import create_app
from test_api import seed_jane

BODY = {"template": "resume-classic", "format": "markdown"}


class NoBrowser(TextRenderer):
    format = "nobrowser"

    def render(self, doc: Document, style: Style) -> bytes:
        raise RendererUnavailable("no browser here")


def open_client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path, renderers=[NoBrowser()]))
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


def test_saving_returns_a_record_and_the_file_downloads_as_rendered(client: TestClient) -> None:
    res = save(client, label="For Acme")
    assert res.status_code == 201
    record = res.json()
    assert set(record) == {"id", "label", "template", "format", "filename", "created_at", "ats_issues"}
    assert record["label"] == "For Acme" and record["filename"] == "Jane-Doe-Resume.md" and record["ats_issues"] == []
    assert len(record["id"]) == 32

    file = client.get(f"/api/saved-documents/{record['id']}/file")
    assert file.status_code == 200 and file.headers["content-type"].startswith("text/markdown")
    assert file.headers["content-disposition"] == 'attachment; filename="Jane-Doe-Resume.md"'
    assert file.content == client.post("/api/documents/render", json=BODY).content


def test_an_empty_label_falls_back_to_the_file_name_without_extension(client: TestClient) -> None:
    assert save(client).json()["label"] == "Jane-Doe-Resume"
    assert save(client, label="   ").json()["label"] == "Jane-Doe-Resume"


def test_the_list_is_newest_first_and_survives_a_restart(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        seed_jane(client)
        first = save(client, label="first").json()
        time.sleep(0.01)
        second = save(client, label="second", format="txt").json()
        assert [r["id"] for r in client.get("/api/saved-documents").json()] == [second["id"], first["id"]]
    with open_client(tmp_path) as again:
        listed = again.get("/api/saved-documents").json()
        assert [r["label"] for r in listed] == ["second", "first"]
        assert again.get(f"/api/saved-documents/{first['id']}/file").content.startswith(b"# Jane Doe")


def test_the_list_is_empty_before_anything_is_saved(client: TestClient) -> None:
    assert client.get("/api/saved-documents").json() == []


def test_deleting_removes_the_record_and_the_file(client: TestClient) -> None:
    keep, gone = save(client, label="keep").json(), save(client, label="gone").json()
    assert client.delete(f"/api/saved-documents/{gone['id']}").status_code == 204
    assert [r["id"] for r in client.get("/api/saved-documents").json()] == [keep["id"]]
    assert client.get(f"/api/saved-documents/{gone['id']}/file").status_code == 404
    assert client.delete(f"/api/saved-documents/{gone['id']}").status_code == 404
    assert client.get(f"/api/saved-documents/{keep['id']}/file").status_code == 200


@pytest.mark.parametrize("doc_id", ["0" * 32, "abc", "A" * 32, "..", "..%2F..%2Fevents.jsonl", "0" * 31 + "g"])
def test_unknown_or_malformed_ids_are_404(client: TestClient, doc_id: str) -> None:
    assert client.get(f"/api/saved-documents/{doc_id}/file").status_code == 404
    assert client.delete(f"/api/saved-documents/{doc_id}").status_code == 404


def test_unknown_template_or_format_is_404_and_a_missing_renderer_is_503(client: TestClient) -> None:
    assert save(client, template="nope").status_code == 404
    assert save(client, format="nope").status_code == 404
    assert save(client, format="nobrowser").status_code == 503
    assert client.get("/api/saved-documents").json() == []


def test_a_failing_ats_check_is_recorded_with_the_record(client: TestClient) -> None:
    rendered = client.post("/api/documents/render", json={**BODY, "format": "txt"})
    expected = [c for c in rendered.headers.get("x-ats-issues", "").split(",") if c]
    assert save(client, format="txt").json()["ats_issues"] == expected


def skill_ids(client: TestClient) -> dict[str, str]:
    profile = client.get("/api/profile").json()
    return dict(zip(profile["skills"], profile["skill_ids"]))


def render(client: TestClient, **extra) -> str:
    return client.post("/api/documents/render", json={**BODY, **extra}).text


def test_a_skill_selection_decides_which_skills_are_printed(client: TestClient) -> None:
    ids = skill_ids(client)
    assert {"Python", "Kubernetes"} <= ids.keys()
    assert "Python" in render(client) and "Kubernetes" in render(client)
    only = render(client, skill_ids=[ids["Kubernetes"]])
    assert "Kubernetes" in only and "Python" not in only.split("Skills")[-1]
    assert "Skills" not in render(client, skill_ids=[])


def test_an_education_selection_decides_which_entries_are_printed(client: TestClient) -> None:
    education = client.get("/api/profile").json()["education"]
    assert education and "University of Lisbon" in render(client)
    assert "University of Lisbon" not in render(client, education_ids=[])
    assert "University of Lisbon" in render(client, education_ids=[education[0]["id"]])


def test_selections_reach_saved_documents_too(client: TestClient) -> None:
    record = save(client, skill_ids=[skill_ids(client)["Kubernetes"]], education_ids=[]).json()
    saved = client.get(f"/api/saved-documents/{record['id']}/file").text
    assert "University of Lisbon" not in saved and "Python" not in saved.split("Skills")[-1]


def test_preview_honours_the_same_selection(client: TestClient) -> None:
    res = client.post("/api/documents/preview", json={"template": "resume-classic", "education_ids": [], "skill_ids": []})
    assert res.status_code == 200
    text = "\n".join(res.json()["lines"])
    assert "University of Lisbon" not in text
