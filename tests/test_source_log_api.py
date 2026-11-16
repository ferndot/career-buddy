"""The live log of a source's processing: lines per source, a cursor for polling, a bounded buffer."""

import logging
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st

from career_buddy.adapters.jobs.source_log import SourceLog, SourceLogHandler
from career_buddy.web.app import create_app
from llm_support import connect_mock
from test_source_processing_api import TEXT, FakeModel, model, wait_for  # noqa: F401  (model is a fixture)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: FakeModel):  # noqa: F811
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)
    with TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model))) as c:
        yield c


def read(client: TestClient, source: str, since: int = 0) -> dict:
    res = client.get(f"/api/sources/{source}/log", params={"since": since})
    assert res.status_code == 200
    return res.json()


def messages(body: dict) -> list[str]:
    return [line["message"] for line in body["lines"]]


def test_the_log_shows_each_step_and_chunk_while_processing_and_stays_after_it(client, model) -> None:
    connect_mock(client)
    model.gate.clear()
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "processing")
    live = read(client, "ada.txt")
    assert live["status"] == "processing" and live["step"] and live["progress"] < 100
    deadline = 100
    while not any("chunk 1: asking the model" in m for m in messages(live)) and deadline:  # the call starts a moment after the step
        live, deadline = read(client, "ada.txt"), deadline - 1
    assert any("extracting ada.txt:" in m for m in messages(live))
    assert not any("the model listed" in m for m in messages(live))  # the answer is still held back
    model.gate.set()
    wait_for(client, "ada.txt", "ready")
    done = read(client, "ada.txt")
    text = "\n".join(messages(done))
    assert done["status"] == "ready" and done["progress"] == 100 and done["error"] is None
    assert "chunk 1 of" in text and "the model listed 4 entities" in text and "Processing finished" in text
    assert all(set(line) == {"seq", "time", "level", "logger", "message"} for line in done["lines"])
    assert {line["logger"].split(".")[1] for line in done["lines"]} <= {"extraction", "application"}
    datetime.fromisoformat(done["lines"][0]["time"])


def test_lines_are_filed_under_the_source_they_belong_to(client) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    client.post("/api/import/text", json={"text": TEXT, "source": "grace.txt"})
    wait_for(client, "ada.txt", "ready")
    wait_for(client, "grace.txt", "ready")
    ada, grace = "\n".join(messages(read(client, "ada.txt"))), "\n".join(messages(read(client, "grace.txt")))
    assert "extracting ada.txt:" in ada and "grace.txt" not in ada
    assert "extracting grace.txt:" in grace and "ada.txt" not in grace


def test_the_cursor_returns_only_lines_after_it(client) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    everything = read(client, "ada.txt")
    assert len(everything["lines"]) >= 4 and everything["cursor"] == everything["lines"][-1]["seq"]
    first = everything["lines"][0]["seq"]
    rest = read(client, "ada.txt", since=first)
    assert rest["lines"] == everything["lines"][1:]
    assert read(client, "ada.txt", since=everything["cursor"])["lines"] == [] and read(client, "ada.txt", since=everything["cursor"])["cursor"] == everything["cursor"]


def test_a_new_run_replaces_the_earlier_log(client) -> None:
    connect_mock(client)
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "ready")
    first = read(client, "ada.txt")
    client.post("/api/sources/ada.txt/reindex")
    wait_for(client, "ada.txt", "ready")
    second = read(client, "ada.txt", since=first["cursor"])
    assert second["run"] == first["run"] + 1
    assert second["lines"] and all(line["seq"] > first["cursor"] for line in second["lines"])
    assert read(client, "ada.txt")["lines"] == second["lines"]  # nothing of the first run is left


def test_a_failed_extraction_shows_why_in_the_log_without_the_server_detail(client, model) -> None:
    connect_mock(client)
    model.status = 500
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    wait_for(client, "ada.txt", "failed")
    body = read(client, "ada.txt")
    log = "\n".join(messages(body))
    assert body["status"] == "failed" and body["error"] and "answered 500" in log
    assert any(line["level"] == "WARNING" for line in body["lines"])


def test_an_import_without_a_model_logs_its_steps(client) -> None:
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert messages(read(client, "ada.txt"))[0] == "Processing started" and "Processing finished" in messages(read(client, "ada.txt"))[-1]


def test_unknown_sources_have_no_log_and_a_removed_source_loses_its_log(client) -> None:
    assert client.get("/api/sources/nothing.txt/log").status_code == 404
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert read(client, "ada.txt")["lines"]
    assert client.delete("/api/sources/ada.txt").status_code == 204
    assert client.get("/api/sources/ada.txt/log").status_code == 404
    client.post("/api/import/text", json={"text": TEXT, "source": "ada.txt"})
    assert read(client, "ada.txt")["lines"][0]["message"] == "Processing started"


def test_the_buffer_keeps_only_the_latest_lines_of_a_run() -> None:
    log = SourceLog(max_lines=3)
    for n in range(5):
        log.add("a", "INFO", "x", f"line {n}")
    log.add("b", "INFO", "x", "other")
    assert [line["message"] for line in log.read("a")["lines"]] == ["line 2", "line 3", "line 4"]
    log.start("a")
    assert log.read("a")["lines"] == [] and [line["message"] for line in log.read("b")["lines"]] == ["other"]


@given(st.lists(st.text(max_size=30), max_size=40), st.integers(1, 10), st.integers(0, 45))
def test_reading_after_a_cursor_is_the_latest_lines_after_it_in_order(texts: list[str], size: int, skip: int) -> None:
    log = SourceLog(max_lines=size)
    for text in texts:
        log.add("a", "INFO", "x", text)
    kept = texts[-size:] if texts else []
    assert [line["message"] for line in log.read("a")["lines"]] == kept
    after = log.read("a", since=skip)
    assert [line["message"] for line in after["lines"]] == [t for n, t in enumerate(texts, 1) if n > skip][-size:]
    assert after["cursor"] >= skip or not after["lines"]
    seqs = [line["seq"] for line in log.read("a")["lines"]]
    assert seqs == sorted(set(seqs))


def test_records_outside_a_job_are_not_kept() -> None:
    log = SourceLog()
    handler = SourceLogHandler(log)
    logger = logging.getLogger("career_buddy.test_outside")
    logger.addHandler(handler)
    try:
        logger.warning("nobody's job")
    finally:
        logger.removeHandler(handler)
    assert log.read("anything")["lines"] == []
