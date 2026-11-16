"""Blackbox tests over HTTP for /api/llm/*: presets, saving, masking, active selection, test calls (always mocked)."""

import json
import os
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st

from career_graph.web.app import create_app
from llm_support import connect_mock
from test_api import linkedin_zip

FAKE_KEY = "sk-fake-1234567890abcdef-a1f2"
CUSTOM = {"preset": "custom", "label": "My server", "base_url": "http://llm.test/v1", "model": "m", "api_key": FAKE_KEY}


class Server:
    """A TestClient over an app whose LLM traffic goes to `handler`; `seen` records every request."""

    def __init__(self, data_dir: Path, handler=None) -> None:
        self.seen: list[httpx.Request] = []
        self.handler = handler or (lambda r: httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b"}]}))
        self.data_dir = data_dir
        self.client = TestClient(create_app(data_dir, llm_transport=httpx.MockTransport(self.respond)))

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self.handler(request)

    def __enter__(self) -> "Server":
        self.client.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self.client.__exit__(*exc)

    def add(self, **fields) -> dict:
        res = self.client.post("/api/llm/connections", json={**CUSTOM, **fields})
        assert res.status_code == 201, res.text
        return res.json()

    def listing(self) -> dict:
        return self.client.get("/api/llm/connections").json()

    def files_text(self) -> str:
        return "".join(p.read_text(errors="ignore") for p in self.data_dir.glob("*.json"))


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ("BASE_URL", "MODEL", "API_KEY"):
        monkeypatch.delenv(f"CAREER_GRAPH_LLM_{name}", raising=False)
    with Server(tmp_path) as s:
        yield s


def test_providers_lists_every_preset_and_only_local_and_custom_urls_are_editable(server: Server) -> None:
    presets = {p["id"]: p for p in server.client.get("/api/llm/providers").json()}
    assert set(presets) == {"anthropic", "gemini", "ollama", "lmstudio", "llamacpp", "custom"}
    assert set(presets["anthropic"]) == {"id", "label", "base_url", "url_editable", "needs_key", "off_device", "hint"}
    assert presets["anthropic"]["base_url"] == "https://api.anthropic.com/v1"
    assert presets["gemini"]["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert presets["llamacpp"]["base_url"] == "http://localhost:9931/v1" and "8080" in presets["llamacpp"]["hint"]
    assert {i for i, p in presets.items() if p["url_editable"]} == {"ollama", "lmstudio", "llamacpp", "custom"}
    assert {i for i, p in presets.items() if p["needs_key"]} == {"anthropic", "gemini"}


def test_a_saved_connection_comes_back_masked_and_the_key_is_not_in_the_settings_file(server: Server) -> None:
    created = server.add()
    listing = server.listing()
    assert listing["active"] is None and listing["connections"] == [created]
    assert created["key_hint"] == "sk-...a1f2" and created["label"] == "My server" and created["preset"] == "custom"
    assert FAKE_KEY not in json.dumps(listing) and FAKE_KEY not in json.dumps(created)
    assert (server.data_dir / "llm-settings.json").exists()
    assert FAKE_KEY not in (server.data_dir / "llm-settings.json").read_text()


@settings(max_examples=15, deadline=None)
@given(key=st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=12, max_size=60))
def test_no_response_ever_carries_a_full_key(key: str) -> None:
    with tempfile.TemporaryDirectory() as data, Server(Path(data)) as server:
        created = server.client.post("/api/llm/connections", json={**CUSTOM, "api_key": key})
        conn_id = created.json()["id"]
        tested = server.client.post("/api/llm/test", json={"id": conn_id})
        patched = server.client.patch(f"/api/llm/connections/{conn_id}", json={"label": "x"})
        for res in (created, patched, tested, server.client.get("/api/llm/connections")):
            assert key not in res.text
            assert key not in res.headers.__str__()


def test_cloud_presets_use_the_fixed_url_need_a_key_and_cannot_be_pointed_elsewhere(server: Server) -> None:
    res = server.client.post("/api/llm/connections", json={"preset": "anthropic", "model": "claude-x"})
    assert res.status_code == 422 and "key" in res.json()["detail"].lower()
    made = server.add(preset="anthropic", base_url="https://evil.example/v1", model="claude-x")
    assert made["base_url"] == "https://api.anthropic.com/v1" and made["off_device"] is True and made["destination"] == "Anthropic"
    res = server.client.patch(f"/api/llm/connections/{made['id']}", json={"base_url": "https://evil.example/v1"})
    assert res.status_code == 422
    assert server.client.post("/api/llm/connections", json={**CUSTOM, "preset": "nope"}).status_code == 422
    assert server.client.post("/api/llm/connections", json={**CUSTOM, "model": ""}).status_code == 422


def test_changing_the_url_clears_the_key_but_changing_the_model_keeps_it(server: Server) -> None:
    conn_id = server.add()["id"]
    kept = server.client.patch(f"/api/llm/connections/{conn_id}", json={"model": "other", "label": "Renamed"}).json()
    assert kept["key_hint"] == "sk-...a1f2" and kept["model"] == "other" and kept["label"] == "Renamed"
    moved = server.client.patch(f"/api/llm/connections/{conn_id}", json={"base_url": "http://other.test/v1"}).json()
    assert moved["key_hint"] is None and moved["base_url"] == "http://other.test/v1"
    assert FAKE_KEY not in server.files_text()
    server.client.post("/api/llm/test", json={"id": conn_id})
    assert "authorization" not in server.seen[-1].headers  # the old key did not follow the URL
    again = server.client.patch(f"/api/llm/connections/{conn_id}", json={"base_url": "http://third.test/v1", "api_key": "fresh-key-0000-9999"}).json()
    assert again["key_hint"] == "fre...9999"


def test_editing_with_a_blank_key_keeps_the_stored_key_and_a_new_key_replaces_it(server: Server) -> None:
    conn_id = server.add()["id"]
    blank = server.client.patch(f"/api/llm/connections/{conn_id}", json={"label": "Edited", "model": "m2", "api_key": ""}).json()
    assert blank["key_hint"] == "sk-...a1f2" and blank["label"] == "Edited" and blank["model"] == "m2"
    server.client.post("/api/llm/test", json={"id": conn_id})
    assert server.seen[-1].headers["authorization"] == f"Bearer {FAKE_KEY}"
    replaced = server.client.patch(f"/api/llm/connections/{conn_id}", json={"api_key": "fresh-key-0000-9999"}).json()
    assert replaced["key_hint"] == "fre...9999"
    server.client.post("/api/llm/test", json={"id": conn_id})
    assert server.seen[-1].headers["authorization"] == "Bearer fresh-key-0000-9999"
    assert "fresh-key-0000-9999" not in (server.data_dir / "llm-settings.json").read_text()


def test_the_model_list_for_a_draft_comes_from_the_server_and_the_key_stays_out_of_the_answer(server: Server) -> None:
    res = server.client.post("/api/llm/test", json={"preset": "custom", "base_url": "http://llm.test/v1", "api_key": FAKE_KEY})
    assert res.status_code == 200 and res.json()["models"] == ["model-a", "model-b"]
    assert FAKE_KEY not in res.text and server.seen[-1].headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert server.listing()["connections"] == []  # asking for models saves nothing


def test_editing_the_active_connection_keeps_it_active(server: Server) -> None:
    conn_id, other = server.add()["id"], server.add(label="Second")["id"]
    server.client.put("/api/llm/active", json={"id": conn_id})
    res = server.client.patch(f"/api/llm/connections/{conn_id}", json={"label": "Renamed", "base_url": "http://moved.test/v1"})
    assert res.status_code == 200
    listing = server.listing()
    assert listing["active"] == conn_id and {c["id"] for c in listing["connections"]} == {conn_id, other}


def test_invalid_edits_get_the_same_errors_as_adding(server: Server) -> None:
    conn_id = server.add()["id"]
    patch = lambda **f: server.client.patch(f"/api/llm/connections/{conn_id}", json=f)  # noqa: E731
    assert patch(model="  ").status_code == 422
    assert patch(base_url="ftp://llm.test/v1").status_code == 422
    assert patch(base_url="http://user:pw@llm.test/v1").status_code == 422
    assert patch(base_url="http://192.168.1.5/v1").status_code == 422
    assert patch(preset="anthropic").status_code == 422
    assert server.client.patch("/api/llm/connections/missing", json={"label": "x"}).status_code == 404
    assert server.listing()["connections"][0]["base_url"] == "http://llm.test/v1"


def test_delete_removes_the_connection_its_key_and_the_active_choice(server: Server) -> None:
    conn_id = server.add()["id"]
    assert server.client.put("/api/llm/active", json={"id": conn_id}).json() == {"active": conn_id}
    assert server.listing()["active"] == conn_id
    assert server.client.delete(f"/api/llm/connections/{conn_id}").status_code == 204
    assert server.listing() == {"active": None, "connections": [], "key_store": "file"}
    assert FAKE_KEY not in server.files_text()
    assert server.client.delete(f"/api/llm/connections/{conn_id}").status_code == 404


def test_only_one_connection_is_active_and_none_is_allowed(server: Server) -> None:
    a, b = server.add()["id"], server.add(label="Second")["id"]
    server.client.put("/api/llm/active", json={"id": a})
    server.client.put("/api/llm/active", json={"id": b})
    assert server.listing()["active"] == b
    assert server.client.put("/api/llm/active", json={"id": "missing"}).status_code == 404
    assert server.client.put("/api/llm/active", json={"id": None}).json() == {"active": None}
    assert server.listing()["active"] is None


def test_the_active_connection_is_the_one_the_app_uses_and_anthropic_gets_native_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CAREER_GRAPH_LLM_BASE_URL", raising=False)

    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps({"text": "Cut build times by 60 percent"})}]}) if request.method == "POST" else httpx.Response(200, json={"data": []})

    with Server(tmp_path, reply) as server:
        server.client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})
        job = {"template": "resume-classic", "job_text": "Requirements:\n- Terraform"}
        assert server.client.post("/api/documents/suggest", json=job).status_code == 503  # no connection yet
        made = server.add(preset="anthropic", model="claude-x", api_key="sk-ant-fake-0000000000")
        server.client.put("/api/llm/active", json={"id": made["id"]})
        assert server.client.post("/api/documents/suggest", json=job).status_code == 200
        request = server.seen[-1]
        assert request.url.host == "api.anthropic.com" and request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "sk-ant-fake-0000000000" and "temperature" not in json.loads(request.content)
        server.client.put("/api/llm/active", json={"id": None})  # back to the offline reader
        assert server.client.post("/api/documents/suggest", json=job).status_code == 503


def test_test_calls_only_the_model_list_sends_no_resume_text_and_returns_the_models(server: Server) -> None:
    conn_id = server.add()["id"]
    res = server.client.post("/api/llm/test", json={"id": conn_id}).json()
    assert res["ok"] is True and res["models"] == ["model-a", "model-b"] and res["message"]
    (request,) = server.seen
    assert request.method == "GET" and str(request.url) == "http://llm.test/v1/models" and request.content == b""
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    draft = server.client.post("/api/llm/test", json={"preset": "custom", "base_url": "http://other.test/v1", "model": "m", "api_key": "draft-key-0000-1111"}).json()
    assert draft["ok"] is True and server.seen[-1].url.host == "other.test"
    assert server.client.post("/api/llm/test", json={"id": "missing"}).status_code == 404


@pytest.mark.parametrize(("status", "words"), [(401, "key"), (403, "key"), (500, "500")])
def test_a_failed_test_says_why_in_plain_words_without_the_key_or_the_server_body(tmp_path: Path, status: int, words: str) -> None:
    with Server(tmp_path, lambda r: httpx.Response(status, text=f"secret detail {FAKE_KEY}")) as server:
        res = server.client.post("/api/llm/test", json={"id": server.add()["id"]})
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False and body["models"] == [] and words in body["message"]
        assert FAKE_KEY not in res.text and "secret detail" not in res.text


def test_a_server_that_is_down_is_reported_as_unreachable(tmp_path: Path) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with Server(tmp_path, down) as server:
        body = server.client.post("/api/llm/test", json={"id": server.add()["id"]}).json()
        assert body["ok"] is False and "reach" in body["message"]


def test_private_addresses_need_a_confirmed_warning_and_metadata_addresses_are_refused(server: Server) -> None:
    lan = {"base_url": "http://192.168.1.20:8080/v1"}
    res = server.client.post("/api/llm/connections", json={**CUSTOM, **lan})
    assert res.status_code == 422 and "private" in res.json()["detail"].lower()
    assert server.client.post("/api/llm/connections", json={**CUSTOM, **lan, "allow_private": True}).status_code == 201
    assert server.client.post("/api/llm/test", json={"preset": "custom", **lan, "model": "m"}).status_code == 422
    for bad in ("http://169.254.169.254/latest", "ftp://llm.test/v1", "http://user:pw@llm.test/v1", "not a url"):
        assert server.client.post("/api/llm/connections", json={**CUSTOM, "base_url": bad, "allow_private": True}).status_code == 422, bad
    for local in ("http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://host.docker.internal:11434/v1"):
        assert server.client.post("/api/llm/connections", json={**CUSTOM, "base_url": local}).status_code == 201, local
    made = server.add(base_url="http://localhost:11434/v1", preset="ollama")
    assert made["off_device"] is False and made["destination"] == "localhost"


def test_environment_variables_show_up_as_a_read_only_connection_that_is_active_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CAREER_GRAPH_LLM_BASE_URL", "http://env.test/v1")
    monkeypatch.setenv("CAREER_GRAPH_LLM_MODEL", "env-model")
    monkeypatch.setenv("CAREER_GRAPH_LLM_API_KEY", FAKE_KEY)
    with Server(tmp_path) as server:
        listing = server.listing()
        (env,) = listing["connections"]
        assert listing["active"] == "env" and env["id"] == "env" and env["read_only"] is True
        assert env["base_url"] == "http://env.test/v1" and env["model"] == "env-model" and FAKE_KEY not in json.dumps(listing)
        assert server.client.patch("/api/llm/connections/env", json={"model": "x"}).status_code == 409
        assert server.client.delete("/api/llm/connections/env").status_code == 409
        assert server.client.post("/api/llm/test", json={"id": "env"}).json()["ok"] is True
        assert server.seen[-1].headers["authorization"] == f"Bearer {FAKE_KEY}"
        server.client.put("/api/llm/active", json={"id": None})
        assert server.listing()["active"] is None


def test_only_this_computer_can_reach_the_api(server: Server) -> None:
    assert server.client.get("/api/llm/providers", headers={"Host": "evil.example"}).status_code == 400
    assert server.client.get("/api/llm/providers", headers={"Host": "localhost:8000"}).status_code == 200


def test_the_fallback_key_file_is_private_to_the_user(server: Server) -> None:
    server.add()
    mode = (server.data_dir / "secrets.json").stat().st_mode & 0o777
    assert mode == 0o600 or os.name == "nt"  # Windows does not enforce POSIX modes


def test_a_mock_helper_connection_round_trips(server: Server) -> None:
    assert connect_mock(server.client) == server.listing()["active"]
