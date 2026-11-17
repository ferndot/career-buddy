"""Reviewing a job posting over HTTP, with the LLM mocked at the transport: what the model is sent, what of its answer survives,
which terms the facts lack, and what happens without a model."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from llm_support import connect_mock
from test_api import seed_jane

POSTING = """Platform Engineer at Initech

Initech builds tools for the enterprise ecosystem.
You have 5+ years of Python, Kubernetes and Terraform. Security clearance is required.
Nice to have: Rust. Join our team and make an impact.
"""
NO_MODEL = "Connect a model in Settings to check the job posting for requirements."


class Model:
    """A mocked model that answers the review with `answer` and records every request it gets."""

    def __init__(self, answer: dict | None = None, status: int = 200) -> None:
        self.answer, self.status = answer or {}, status
        self.requests: list[dict] = []

    def respond(self, request: httpx.Request) -> httpx.Response:
        if self.status != 200:
            return httpx.Response(self.status, text="no")
        self.requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(self.answer)}}]})


@pytest.fixture(autouse=True)
def no_env_llm(monkeypatch) -> None:
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)


def open_client(tmp_path: Path, model: Model | None) -> TestClient:
    client = TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model.respond) if model else None))
    client.__enter__()
    seed_jane(client)  # before the model connects, so the offline reader finishes the import in the call
    if model:
        connect_mock(client)
    return client


def review(tmp_path: Path, answer: dict) -> tuple[dict, Model]:
    model = Model({"title": "Platform Engineer", "company": "Initech", **answer})
    client = open_client(tmp_path, model)
    try:
        res = client.post("/api/fit", json={"job_text": POSTING})
        assert res.status_code == 200, res.text
        return res.json(), model
    finally:
        client.__exit__(None, None, None)


def refused(tmp_path: Path, model: Model | None) -> dict:
    client = open_client(tmp_path, model)
    try:
        res = client.post("/api/fit", json={"job_text": POSTING})
        assert res.status_code == 503 and res.json()["code"] == "llm_unavailable"
        return res.json()
    finally:
        client.__exit__(None, None, None)


def test_the_model_is_sent_the_posting_and_none_of_the_persons_facts(tmp_path: Path) -> None:
    _, model = review(tmp_path, {"must_have": ["Python"]})
    assert len(model.requests) == 1
    messages = model.requests[0]["messages"]
    assert json.loads(messages[-1]["content"]) == {"posting": POSTING.strip()}
    sent = json.dumps(model.requests[0])
    for private in ("Jane", "Acme", "Globex", "Lisbon", "Cut build times", "Platform engineer", "Builds reliable"):
        assert private not in sent
    assert "company name" in messages[0]["content"] and "12" in messages[0]["content"]  # the prompt's rules and caps


def test_a_term_the_posting_does_not_contain_is_dropped(tmp_path: Path) -> None:
    got, _ = review(tmp_path, {"must_have": ["Terraform", "Haskell"], "nice_to_have": ["Rust", "Erlang"]})
    assert got["must_have"] == ["Terraform"] and got["nice_to_have"] == ["Rust"]


def test_the_company_and_the_title_and_generic_words_are_dropped(tmp_path: Path) -> None:
    junk = ["Initech", "initech's", "Platform Engineer", "ecosystem", "enterprise", "team", "impact", "x"]
    got, _ = review(tmp_path, {"must_have": [*junk, "Kubernetes"]})
    assert got["must_have"] == ["Kubernetes"] and got["company"] == "Initech"


def test_the_missing_terms_are_only_must_haves_the_facts_lack(tmp_path: Path) -> None:
    # Jane's facts name Python and Kubernetes, and no Terraform or clearance. Rust is a nice-to-have she lacks.
    asked = ["5+ years of Python", "Kubernetes", "Terraform", "Security clearance"]
    got, _ = review(tmp_path, {"must_have": asked, "nice_to_have": ["Rust"]})
    assert got["must_have"] == asked
    assert got["missing_must_have"] == ["Terraform", "Security clearance"]
    assert got["missing_nice_to_have"] == ["Rust"]


def test_without_a_model_the_review_is_503_with_a_stable_code_and_no_terms(tmp_path: Path) -> None:
    body = refused(tmp_path, None)
    assert body["detail"] == NO_MODEL and "must_have" not in body


def test_a_model_that_fails_is_503_too(tmp_path: Path) -> None:
    refused(tmp_path, Model(status=500))
