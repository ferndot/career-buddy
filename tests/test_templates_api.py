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
    "resume-sidebar": {},
    "resume-modern": {},
    "cover-letter": {},
    "cover-letter-modern": {},
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
    assert not any(t["required"] for t in listed.values())
    assert listed["cover-letter"]["optional"] == ["recipient"]
    assert listed["resume-classic"]["kind"] == "resume" and listed["cover-letter-modern"]["kind"] == "letter"
    assert listed["resume-sidebar"]["label"] == "Sidebar resume"


def test_every_template_carries_its_layout_and_its_own_writer_instructions(client: TestClient) -> None:
    listed = {t["id"]: t for t in client.get("/api/templates").json()}
    resumes = [t for t in listed.values() if t["kind"] == "resume"]
    letters = [t for t in listed.values() if t["kind"] == "letter"]
    assert len(resumes) >= 3 and len(letters) >= 2
    assert len({(t["layout"]["header"], tuple(t["layout"]["side"])) for t in resumes}) == len(resumes)  # clearly different layouts
    assert len({t["instructions"] for t in listed.values()}) == len(listed) and all(t["instructions"] for t in listed.values())
    assert listed["resume-sidebar"]["layout"]["side"] == ["Education", "Skills"]
    assert [s["id"] for s in listed["cover-letter"]["styles"]] == ["direct", "narrative", "formal"]
    assert all(s["label"] and s["instructions"] for s in listed["cover-letter"]["styles"]) and listed["resume-classic"]["styles"] == []
    assert listed["resume-modern"]["sections"] == ["Summary", "Experience", "Education", "Skills"] and listed["cover-letter"]["sections"] == []


def test_the_email_cover_letter_is_gone(client: TestClient) -> None:
    assert "cover-letter-email" not in {t["id"] for t in client.get("/api/templates").json()}
    assert render(client, "cover-letter", "txt").status_code == 200
    res = client.post("/api/documents/render", json={"template": "cover-letter-email", "format": "txt", "inputs": COMPANY})
    assert res.status_code == 404


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


@pytest.mark.parametrize("template", ["cover-letter", "cover-letter-modern"])
def test_a_letter_without_a_writer_is_the_name_and_location_and_an_empty_body(client: TestClient, template: str) -> None:
    """No code writes a letter's words: the inputs and the job are for the writer, and nothing of them is printed."""
    job = "Requirements:\n- Kubernetes migrations\n- Terraform"
    text = render(client, template, "txt", job_text=job, inputs={**COMPANY, "recipient": "Alex Kim"}).text
    assert text.split() == ["Jane", "Doe", "Lisbon,", "Portugal"]
    assert render(client, template, "txt").text == text


def test_filenames_say_what_the_document_is(client: TestClient) -> None:
    names = {t: render(client, t, "txt").headers["content-disposition"] for t in INPUTS}
    assert names["cover-letter"].endswith('-Cover-Letter.txt"')
    assert names["cover-letter-modern"].endswith('-Cover-Letter.txt"')
    assert names["resume-sidebar"].endswith('-Resume.txt"')



def test_other_templates_ignore_unknown_inputs(client: TestClient) -> None:
    res = render(client, "resume-classic", "txt", inputs={"company": "Initech"})
    assert res.status_code == 200


def test_templates_endpoint_says_which_are_ats_safe(client: TestClient) -> None:
    listed = {t["id"]: t["ats_safe"] for t in client.get("/api/templates").json()}
    assert listed == dict.fromkeys(INPUTS, True)
