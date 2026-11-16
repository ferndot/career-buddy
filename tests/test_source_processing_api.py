"""Source processing over HTTP: CORS for the separate frontend, status in the source list, background import and reindex."""

import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from llm_support import connect_mock

TEXT = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first algorithm\n"
FRONTEND = "http://localhost:5173"


def extraction(title: str) -> dict:
    """The model's answer in redstring's entity and relationship shape."""
    content = {
        "entities": [
            {"name": "Ada Lovelace", "entity_type": "Person"},
            {"name": title, "entity_type": "Position", "properties": {"period": "2010 - 2015"}},
            {"name": "Analytical Society", "entity_type": "Organization"},
            {"name": "Wrote the first algorithm", "entity_type": "Achievement"},
        ],
        "relationships": [
            {"source_name": "Ada Lovelace", "target_name": title, "relationship_type": "HAS_POSITION"},
            {"source_name": title, "target_name": "Analytical Society", "relationship_type": "AT"},
            {"source_name": title, "target_name": "Wrote the first algorithm", "relationship_type": "ACHIEVED"},
        ],
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


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
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)
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
    monkeypatch.setenv("CAREER_BUDDY_CORS_ORIGINS", "https://app.test, https://other.test")
    with TestClient(create_app(tmp_path)) as c:
        assert c.get("/api/sources", headers={"Origin": "https://other.test"}).headers["access-control-allow-origin"] == "https://other.test"
        assert "access-control-allow-origin" not in c.get("/api/sources", headers={"Origin": FRONTEND}).headers


def test_the_source_list_carries_status_progress_step_and_error(client) -> None:
    assert client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"}).json() == {"facts": 4}
    assert listing(client)["ada.txt"] == {"source": "ada.txt", "facts": 4, "status": "ready", "progress": 100, "step": "Done", "error": None}


def test_an_import_with_a_model_returns_a_queued_source_and_becomes_ready(client, model) -> None:
    connect_mock(client)
    model.gate.clear()
    res = client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert res.status_code == 202
    assert res.json()["source"] == "ada.txt" and res.json()["status"] in ("queued", "processing") and res.json()["error"] is None
    held = listing(client)["ada.txt"]
    assert held["status"] in ("queued", "processing") and held["progress"] in (None, 0) and held["step"]
    model.gate.set()
    ready = wait_for(client, "ada.txt", "ready")
    assert ready["progress"] == 100 and ready["facts"] > 0 and ready["error"] is None
    assert titles(client) == ["Analyst"]


def test_a_file_import_with_a_model_is_queued_too(client) -> None:
    connect_mock(client)
    res = client.post("/api/import/file", files={"file": ("resume.txt", TEXT.encode(), "text/plain")})
    assert res.status_code == 202 and res.json()["source"] == "resume.txt"
    wait_for(client, "resume.txt", "ready")


def test_reindex_adds_what_is_new_and_keeps_edits_to_what_was_there(client, model) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    assert titles(client) == ["Analyst"]
    (analyst,) = client.get("/api/facts", params={"kind": "Position"}).json()
    client.patch(f"/api/facts/{analyst['id']}", json={"title": "Chief Analyst"})
    model.title = "Mathematician"
    res = client.post("/api/sources/ada.txt/reindex")
    assert res.status_code == 202 and res.json()["source"] == "ada.txt" and res.json()["status"] in ("queued", "processing")
    wait_for(client, "ada.txt", "ready")
    assert sorted(titles(client)) == ["Chief Analyst", "Mathematician"]  # the edited fact stays, the re-extraction adds a new one


def test_reindex_without_a_model_uses_the_offline_reader(client) -> None:
    client.post("/api/import/file", files={"file": ("resume.txt", TEXT.encode(), "text/plain")})
    res = client.post("/api/sources/resume.txt/reindex")
    assert res.status_code == 202
    assert wait_for(client, "resume.txt", "ready")["facts"] == 4
    assert titles(client) == ["Analyst"]


def test_reindex_of_an_unknown_source_is_404(client) -> None:
    assert client.post("/api/sources/nothing.txt/reindex").status_code == 404


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


def test_a_first_import_that_failed_can_be_retried(client, model) -> None:
    connect_mock(client)
    model.status = 503
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert wait_for(client, "ada.txt", "failed")["facts"] == 0
    model.status = 200
    assert client.post("/api/sources/ada.txt/reindex").status_code == 202
    wait_for(client, "ada.txt", "ready")
    assert titles(client) == ["Analyst"]
def app_client(tmp_path, model):
    return TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model)))


def test_a_failed_first_import_is_listed_as_failed_and_returned_by_the_sources_endpoint(client, model) -> None:
    connect_mock(client)
    model.status = 503
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "failed")
    listed = {s["source"]: s for s in client.get("/api/sources").json()}
    assert listed["ada.txt"]["status"] == "failed" and listed["ada.txt"]["error"] and listed["ada.txt"]["facts"] == 0


def test_a_source_that_failed_before_a_restart_can_be_retried_after_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model) -> None:
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)
    model.status = 503
    with app_client(tmp_path, model) as first:
        connect_mock(first)
        first.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
        wait_for(first, "ada.txt", "failed")
    model.status = 200
    with app_client(tmp_path, model) as second:  # job states are in memory, so only the registration remains
        assert listing(second)["ada.txt"]["facts"] == 0
        assert second.post("/api/sources/ada.txt/reindex").status_code == 202
        wait_for(second, "ada.txt", "ready")
        assert titles(second) == ["Analyst"]


def test_importing_a_removed_source_again_registers_it_again(client, model) -> None:
    connect_mock(client)
    model.status = 503
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "failed")
    assert client.delete("/api/sources/ada.txt").status_code == 204
    assert "ada.txt" not in listing(client)
    assert client.post("/api/sources/ada.txt/reindex").status_code == 404
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "failed")
    model.status = 200
    assert client.post("/api/sources/ada.txt/reindex").status_code == 202
    wait_for(client, "ada.txt", "ready")
    assert titles(client) == ["Analyst"]
