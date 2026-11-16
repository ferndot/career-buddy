"""Blackbox tests over HTTP: tailoring, marker cleaning and LLM suggestions (always a mocked LLM)."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from llm_support import connect_mock
from test_api import linkedin_zip

JOB = "Requirements:\n- Kubernetes migrations\n- Terraform"
DIRTY = "Delve into cost data to fix potential leaks​"
CUT, KUBE = "Cut build times by 60%", "Migrated 40 services to Kubernetes"


def reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"text": text})}}]})


def source_of(request: httpx.Request) -> str:
    return json.loads(request.content)["messages"][-1]["content"]


@pytest.fixture(autouse=True)
def no_env_llm(monkeypatch) -> None:
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)


def open_client(tmp_path: Path, handler=None) -> TestClient:
    client = TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(handler) if handler else None))
    client.__enter__()
    if handler:
        connect_mock(client)
    client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
    return client


@pytest.fixture
def client(tmp_path: Path):
    c = open_client(tmp_path)
    yield c
    c.__exit__(None, None, None)


def preview(client: TestClient, **extra) -> dict:
    res = client.post("/api/documents/preview", json={"template": "resume-classic", **extra})
    assert res.status_code == 200, res.text
    return res.json()


def position(client: TestClient, title: str) -> dict:
    return next(p for p in client.get("/api/profile").json()["positions"] if p["title"] == title)


def add_bullet(client: TestClient, title: str) -> str:
    res = client.post("/api/facts", json={"kind": "Achievement", "title": title,
                                          "parent_id": position(client, "Senior Engineer")["id"]})
    return res.json()["id"]


def suggest(client: TestClient) -> dict:
    res = client.post("/api/documents/suggest", json={"template": "resume-classic", "job_text": JOB})
    assert res.status_code == 200, res.text
    return res.json()


def test_bullets_reorder_toward_the_job_and_missing_terms_are_reported_not_added(client) -> None:
    plain = preview(client)["lines"]
    assert plain.index(CUT) < plain.index(KUBE)

    out = preview(client, job_text=JOB)
    assert out["lines"].index(KUBE) < out["lines"].index(CUT)
    assert "kubernetes" in out["tailoring"]["matched"]
    assert "terraform" in out["tailoring"]["missing"] and "kubernetes" not in out["tailoring"]["missing"]

    md = client.post("/api/documents/render", json={"template": "resume-classic", "format": "markdown", "job_text": JOB})
    assert "terraform" not in md.text.lower()
    assert "terraform" not in json.dumps(client.get("/api/facts").json()).lower()


def test_delve_into_is_swapped_potential_is_flagged_and_kept_and_zero_width_is_stripped(client) -> None:
    bullet = add_bullet(client, DIRTY)
    out = preview(client)
    assert "Explore cost data to fix potential leaks" in out["lines"]
    changes = {(m["kind"], m["found"], m["source_fact_id"]) for m in out["markers"]}
    assert {("swap", "Delve into", bullet), ("flag", "potential", bullet)} <= changes
    assert any(m["kind"] == "strip" for m in out["markers"])
    assert {(m["kind"], m["weak"]) for m in out["markers"]} == {("swap", True), ("flag", True), ("strip", False)}
    md = client.post("/api/documents/render", json={"template": "resume-classic", "format": "markdown"}).text
    assert "- Explore cost data to fix potential leaks\n" in md and "​" not in md


def test_rendering_and_previewing_leave_the_facts_unchanged(client) -> None:
    add_bullet(client, DIRTY)
    before = client.get("/api/facts").json()
    preview(client, job_text=JOB)
    for fmt in ("markdown", "docx"):
        client.post("/api/documents/render", json={"template": "resume-classic", "format": fmt, "job_text": JOB})
    assert client.get("/api/facts").json() == before
    assert DIRTY in {f["title"] for f in before}


def test_selection_and_overrides_shape_the_document_without_touching_facts(client) -> None:
    senior = position(client, "Senior Engineer")
    cut = senior["achievement_ids"][senior["achievements"].index(CUT)]
    out = preview(client, selection=[cut], overrides={cut: "Cut build times by 61%", senior["id"]: "Chief"})
    assert "Cut build times by 61%" in out["lines"] and KUBE not in out["lines"]
    assert not any("Chief" in line for line in out["lines"])
    assert CUT in {f["title"] for f in client.get("/api/facts").json()}


def test_compact_template_keeps_three_bullets_per_position(client) -> None:
    for n in range(5):
        add_bullet(client, f"Extra task {n}")
    out = client.post("/api/documents/preview", json={"template": "resume-compact"}).json()
    experience = next(s for s in out["document"]["sections"] if s["title"] == "Experience")
    assert max(len(e["bullets"]) for e in experience["entries"]) == 3


def test_unknown_template_is_404(client) -> None:
    assert client.post("/api/documents/preview", json={"template": "nope"}).status_code == 404


def test_suggest_is_503_without_an_llm(client) -> None:
    res = client.post("/api/documents/suggest", json={"template": "resume-classic", "job_text": JOB})
    assert res.status_code == 503


def test_a_suggestion_with_a_new_number_is_rejected_and_one_that_keeps_numbers_is_accepted(tmp_path: Path) -> None:
    answers = {CUT: "Cut build times by 75%", KUBE: "Moved 40 services to Kubernetes"}
    with open_client(tmp_path, lambda request: reply(answers.get(source_of(request), source_of(request)))) as client:
        senior = position(client, "Senior Engineer")
        ids = dict(zip(senior["achievements"], senior["achievement_ids"]))
        body = suggest(client)
        assert body["suggestions"] == [{"fact_id": ids[KUBE], "before": KUBE, "after": "Moved 40 services to Kubernetes"}]
        assert [r["fact_id"] for r in body["rejected"]] == [ids[CUT]]
        assert "number" in body["rejected"][0]["reasons"][0]
        assert CUT in {f["title"] for f in client.get("/api/facts").json()}


def test_an_ambiguous_word_in_a_suggestion_is_flag_only_so_it_is_kept_and_not_regenerated(tmp_path: Path) -> None:
    calls: list[str] = []
    answers = {KUBE: "Migrated 40 potential services to Kubernetes"}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(source_of(request))
        return reply(answers.get(source_of(request), source_of(request)))

    with open_client(tmp_path, handler) as client:
        senior = position(client, "Senior Engineer")
        ids = dict(zip(senior["achievements"], senior["achievement_ids"]))
        body = suggest(client)
    assert body["suggestions"] == [{"fact_id": ids[KUBE], "before": KUBE, "after": answers[KUBE]}]
    assert body["rejected"] == [] and calls.count(KUBE) == 1


def test_an_em_dash_in_a_suggestion_becomes_a_comma(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return reply("Moved 40 services to Kubernetes — fast" if source_of(request) == KUBE else source_of(request))

    with open_client(tmp_path, handler) as client:
        body = suggest(client)
    assert [s["after"] for s in body["suggestions"]] == ["Moved 40 services to Kubernetes, fast"]


def test_an_unreachable_llm_is_503(tmp_path: Path) -> None:
    with open_client(tmp_path, lambda request: httpx.Response(500)) as client:
        res = client.post("/api/documents/suggest", json={"template": "resume-classic", "job_text": JOB})
    assert res.status_code == 503


def test_summary_and_headline_overrides_change_the_rendered_document_without_touching_facts(client) -> None:
    out = preview(client, overrides={"summary": "Builds data platforms", "headline": "Staff engineer"})
    assert "Builds data platforms" in out["lines"] and "Staff engineer" in out["lines"]
    assert "Builds reliable data pipelines" not in out["lines"]
    md = client.post("/api/documents/render", json={"template": "resume-classic", "format": "markdown",
                                                    "overrides": {"summary": "Builds data platforms"}}).text
    assert "Builds data platforms" in md
    person = client.get("/api/profile").json()
    assert person["attributes"]["summary"] == "Builds reliable data pipelines"
    assert preview(client, overrides={"summary": "  "})["lines"] == preview(client)["lines"]  # blank: ignored


def test_a_paragraph_override_goes_through_the_same_marker_rules_as_a_bullet(client) -> None:
    person = client.get("/api/profile").json()["id"]
    bullet = position(client, "Senior Engineer")["achievement_ids"][0]
    wording = "Delve into data with potential care​"
    out = preview(client, overrides={"summary": wording, bullet: wording})
    assert out["lines"].count("Explore data with potential care") == 2
    for owner in (person, bullet):
        changes = {(m["kind"], m["found"]) for m in out["markers"] if m["source_fact_id"] == owner}
        assert {("swap", "Delve into"), ("flag", "potential")} <= changes and any(k == "strip" for k, _ in changes)


def test_an_accepted_suggestion_is_an_override_and_the_stored_bullet_stays(tmp_path: Path) -> None:
    answers = {KUBE: "Moved 40 services to Kubernetes"}
    with open_client(tmp_path, lambda request: reply(answers.get(source_of(request), source_of(request)))) as client:
        [accepted] = suggest(client)["suggestions"]
        out = preview(client, job_text=JOB, overrides={accepted["fact_id"]: accepted["after"]})
        assert accepted["after"] in out["lines"] and KUBE not in out["lines"]
        assert KUBE in {f["title"] for f in client.get("/api/facts").json()}
        again = client.post("/api/documents/suggest", json={"template": "resume-classic", "job_text": JOB,
                                                            "overrides": {accepted["fact_id"]: accepted["after"]}})
        assert accepted["fact_id"] not in {s["fact_id"] for s in again.json()["suggestions"]}  # offered once


def test_wording_is_written_from_what_the_achievement_states_not_only_its_bullet(tmp_path: Path) -> None:
    seen: list[str] = []
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(source_of(request))
        prompts.append(json.loads(request.content)["messages"][0]["content"])
        return reply(source_of(request))

    with open_client(tmp_path, handler) as client:
        senior = position(client, "Senior Engineer")
        client.post("/api/facts", json={"kind": "Achievement", "title": "Moved CI pipeline onto Bazel",
                                        "parent_id": senior["id"], "attributes": {"result": "60%", "tools": "Bazel"}})
        suggest(client)
    assert any("Result: 60%" in s and "Tools: Bazel" in s for s in seen)
    assert any("Kubernetes migrations" in p for p in prompts)  # the job posting reaches the wording prompt


def test_cover_letter_bullets_get_llm_wording_like_the_resume(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return reply("Moved 40 services to Kubernetes" if source_of(request) == KUBE else source_of(request))

    with open_client(tmp_path, handler) as client:
        senior = position(client, "Senior Engineer")
        kube_id = dict(zip(senior["achievements"], senior["achievement_ids"]))[KUBE]
        res = client.post("/api/documents/suggest", json={"template": "cover-letter", "job_text": JOB})
    assert res.status_code == 200, res.text
    assert res.json()["suggestions"] == [{"fact_id": kube_id, "before": KUBE, "after": "Moved 40 services to Kubernetes"}]
