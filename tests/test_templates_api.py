"""HTTP front door for the full template set: every template in every format, required inputs, ATS warnings."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from test_api import seed_jane

FORMATS = ["docx", "pdf", "txt", "markdown", "html"]
COMPANY = {"company": "Initech", "role": "Platform Engineer"}
INPUTS = {
    "resume-classic": {},
    "resume-compact": {},
    "resume-hybrid": {},
    "cover-letter": {},
    "cover-letter-email": COMPANY,
}
REQUIRED = {
    "cover-letter-email": ["company", "role"],
}


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as client:
        seed_jane(client)
        yield client


def render(client: TestClient, template: str, fmt: str, **extra):
    body = {"template": template, "format": fmt, "inputs": INPUTS[template], **extra}
    return client.post("/api/documents/render", json=body)


def test_templates_endpoint_lists_ids_formats_and_required_inputs(client: TestClient) -> None:
    listed = {t["id"]: t for t in client.get("/api/templates").json()}
    assert set(listed) == set(INPUTS)
    assert all(sorted(t["formats"]) == sorted(FORMATS) for t in listed.values())
    assert {tid: t["required"] for tid, t in listed.items() if t["required"]} == REQUIRED
    assert listed["cover-letter"]["optional"] == ["recipient"]
    assert listed["resume-classic"]["kind"] == "resume" and listed["cover-letter-email"]["kind"] == "letter"
    assert listed["resume-hybrid"]["label"] == "Hybrid resume"


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("template", list(INPUTS))
def test_every_template_renders_in_every_format_and_passes_the_ats_check(
    client: TestClient, chromium, template: str, fmt: str
) -> None:
    res = render(client, template, fmt)
    assert res.status_code == 200, res.text
    assert res.headers["content-disposition"].startswith('attachment; filename="Jane-Doe-')
    assert len(res.content) > (20 if template.startswith("cover-letter") else 100)  # a letter nobody wrote is just its header
    assert "x-ats-issues" not in res.headers  # a passing check sends no warning


@pytest.mark.parametrize("template", list(REQUIRED))
def test_a_missing_required_input_is_422_and_names_what_is_missing(client: TestClient, template: str) -> None:
    for fmt, path in (("txt", "render"), ("txt", "check"), (None, "preview")):
        body = {"template": template, **({"format": fmt} if fmt else {}), "inputs": {}}
        res = client.post(f"/api/documents/{path}", json=body)
        assert res.status_code == 422, (path, res.text)
        assert all(name in res.json()["detail"] for name in REQUIRED[template])


def test_a_blank_required_input_counts_as_missing(client: TestClient) -> None:
    res = client.post("/api/documents/render", json={"template": "cover-letter-email", "format": "txt",
                                                      "inputs": {"company": "Initech", "role": "   "}})
    assert res.status_code == 422 and "role" in res.json()["detail"]


@pytest.mark.parametrize("template", ["cover-letter", "cover-letter-email"])
def test_a_letter_without_a_writer_is_the_name_and_location_and_an_empty_body(client: TestClient, template: str) -> None:
    """No code writes a letter's words: the inputs and the job are for the writer, and nothing of them is printed."""
    job = "Requirements:\n- Kubernetes migrations\n- Terraform"
    text = render(client, template, "txt", job_text=job, inputs={**COMPANY, "recipient": "Alex Kim"}).text
    assert text.split() == ["Jane", "Doe", "Lisbon,", "Portugal"]
    assert render(client, template, "txt").text == text


def test_filenames_say_what_the_document_is(client: TestClient) -> None:
    names = {t: render(client, t, "txt").headers["content-disposition"] for t in INPUTS}
    assert names["cover-letter"].endswith('-Cover-Letter.txt"')
    assert names["resume-hybrid"].endswith('-Resume.txt"')


def test_the_hybrid_resume_puts_skills_before_experience(client: TestClient) -> None:
    text = render(client, "resume-hybrid", "txt").text
    assert text.index("\nSkills\n") < text.index("\nExperience\n")


def test_other_templates_ignore_unknown_inputs(client: TestClient) -> None:
    res = render(client, "resume-classic", "txt", inputs={"company": "Initech"})
    assert res.status_code == 200
