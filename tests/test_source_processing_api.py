"""Source processing over HTTP: CORS for the separate frontend, status in the source list, background import and reindex."""

import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_graph.web.app import create_app
from llm_support import connect_mock
from test_api import linkedin_zip

TEXT = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first algorithm\n"
FRONTEND = "http://localhost:5173"


def extraction(title: str) -> dict:
    position = {"title": title, "organization": "Analytical Society", "period": "2010 - 2015", "achievements": ["Wrote the first algorithm"], "skills": []}
    return {"choices": [{"message": {"content": json.dumps({"name": "Ada Lovelace", "headline": "", "skills": [], "positions": [position], "education": []})}}]}


class FakeModel:
    """The LLM server behind the mocked transport. `gate` holds answers back; `status` makes it fail."""

    def __init__(self) -> None:
        self.title = "Analyst"
        self.status = 200
        self.gate = threading.Event()
        self.gate.set()

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        while not self.gate.is_set():
            await asyncio.sleep(0.01)
        if self.status != 200:
            return httpx.Response(self.status, text="secret server detail")
        return httpx.Response(200, json=extraction(self.title))


@pytest.fixture
def model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: FakeModel):
    monkeypatch.delenv("CAREER_GRAPH_LLM_BASE_URL", raising=False)
    with TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model))) as c:
        yield c


def listing(client: TestClient) -> dict[str, dict]:
    return {s["source"]: s for s in client.get("/api/sources").json()}


def wait_for(client: TestClient, source: str, status: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = listing(client).get(source)
        if record and record["status"] == status:
            return record
        time.sleep(0.02)
    raise AssertionError(f"{source} never became {status}: {listing(client).get(source)}")


def titles(client: TestClient, kind: str = "Position") -> list[str]:
    return [f["title"] for f in client.get("/api/facts", params={"kind": kind}).json()]


def test_cors_preflight_from_the_frontend_origin_is_allowed_and_other_origins_are_not(client) -> None:
    ask = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    allowed = client.options("/api/sources/a.txt/reindex", headers={"Origin": FRONTEND, **ask})
    assert allowed.status_code == 200 and allowed.headers["access-control-allow-origin"] == FRONTEND
    assert "POST" in allowed.headers["access-control-allow-methods"]
    other = client.options("/api/sources", headers={"Origin": "http://evil.example", **ask})
    assert "access-control-allow-origin" not in other.headers
    assert client.get("/api/sources", headers={"Origin": "http://127.0.0.1:5173"}).headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_origins_come_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREER_GRAPH_CORS_ORIGINS", "https://app.test, https://other.test")
    with TestClient(create_app(tmp_path)) as c:
        assert c.get("/api/sources", headers={"Origin": "https://other.test"}).headers["access-control-allow-origin"] == "https://other.test"
        assert "access-control-allow-origin" not in c.get("/api/sources", headers={"Origin": FRONTEND}).headers


def test_the_source_list_carries_status_progress_step_and_error(client) -> None:
    assert client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"}).json() == {"facts": 4}
    assert listing(client)["ada.txt"] == {"source": "ada.txt", "facts": 4, "status": "ready", "progress": 100, "step": "Done", "error": None}
    client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
    assert listing(client)["linkedin-export"]["status"] == "ready"


def test_an_import_with_a_model_returns_a_queued_source_and_becomes_ready(client, model) -> None:
    connect_mock(client)
    model.gate.clear()
    res = client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert res.status_code == 202
    assert res.json()["source"] == "ada.txt" and res.json()["status"] in ("queued", "processing") and res.json()["error"] is None
    held = listing(client)["ada.txt"]
    assert held["status"] in ("queued", "processing") and held["progress"] < 100 and held["step"]
    model.gate.set()
    ready = wait_for(client, "ada.txt", "ready")
    assert ready["progress"] == 100 and ready["facts"] > 0 and ready["error"] is None
    assert titles(client) == ["Analyst"]


def test_a_file_import_with_a_model_is_queued_too(client) -> None:
    connect_mock(client)
    res = client.post("/api/import/file", files={"file": ("resume.txt", TEXT.encode(), "text/plain")})
    assert res.status_code == 202 and res.json()["source"] == "resume.txt"
    wait_for(client, "resume.txt", "ready")


def test_reindex_replaces_the_facts_of_that_source_with_a_new_extraction(client, model) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    assert titles(client) == ["Analyst"]
    model.title = "Mathematician"
    res = client.post("/api/sources/ada.txt/reindex")
    assert res.status_code == 202 and res.json()["source"] == "ada.txt" and res.json()["status"] in ("queued", "processing")
    wait_for(client, "ada.txt", "ready")
    assert titles(client) == ["Mathematician"]


def test_reindex_without_a_model_uses_the_offline_reader(client) -> None:
    client.post("/api/import/file", files={"file": ("resume.txt", TEXT.encode(), "text/plain")})
    res = client.post("/api/sources/resume.txt/reindex")
    assert res.status_code == 202
    assert wait_for(client, "resume.txt", "ready")["facts"] == 4
    assert titles(client) == ["Analyst"]


def test_reindex_of_an_unknown_source_is_404(client) -> None:
    assert client.post("/api/sources/nothing.txt/reindex").status_code == 404


def test_reindex_of_a_source_with_no_stored_original_is_422(client) -> None:
    client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
    assert client.post("/api/sources/linkedin-export/reindex").status_code == 422


def test_reindex_while_processing_is_409_and_so_is_removing_the_source(client, model) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    model.gate.clear()
    assert client.post("/api/sources/ada.txt/reindex").status_code == 202
    assert client.post("/api/sources/ada.txt/reindex").status_code == 409
    assert client.delete("/api/sources/ada.txt").status_code == 409
    assert client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"}).status_code == 409
    model.gate.set()
    wait_for(client, "ada.txt", "ready")
    assert client.post("/api/sources/ada.txt/reindex").status_code == 202


def test_a_failing_extraction_marks_the_source_failed_with_a_readable_error_and_no_leak(client, model) -> None:
    connect_mock(client)
    model.status = 500
    assert client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"}).status_code == 202
    failed = wait_for(client, "ada.txt", "failed")
    assert failed["error"] == "The model server answered with status 500" and failed["facts"] == 0
    assert "secret server detail" not in json.dumps(listing(client)) and "Traceback" not in json.dumps(listing(client))
    assert client.delete("/api/sources/ada.txt").status_code == 204  # a failed import can be dismissed
    assert "ada.txt" not in listing(client)


def test_a_failed_reindex_keeps_the_earlier_facts_and_a_retry_can_succeed(client, model) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    model.status = 503
    client.post("/api/sources/ada.txt/reindex")
    assert wait_for(client, "ada.txt", "failed")["error"]
    assert titles(client) == ["Analyst"]
    model.status = 200
    assert client.post("/api/sources/ada.txt/reindex").status_code == 202
    wait_for(client, "ada.txt", "ready")
