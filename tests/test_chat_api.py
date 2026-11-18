"""The career chat over HTTP (POST /api/chat): the model is mocked at the transport as a tool-calling chat model, and the answer is read as an AG-UI
event stream. Each read tool is checked through the stream; the facts come in through the public import and edit routes."""

import json
from pathlib import Path

import httpx
import pytest
from ag_ui.core import Event
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from career_buddy.web.app import create_app
from llm_support import connect_mock
from test_api import seed_jane

EVENTS = TypeAdapter(Event)


class Model:
    """A scripted tool-calling model. Each reply is text, or a tool call `(name, arguments)`; the last reply repeats. Every request body is kept."""

    def __init__(self, *replies: str | tuple[str, dict], status: int = 200) -> None:
        self.replies, self.status, self.requests = replies, status, []

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if self.status != 200:
            return httpx.Response(self.status, text="no")
        reply = self.replies[min(len(self.requests), len(self.replies)) - 1]
        if isinstance(reply, str):
            message = {"role": "assistant", "content": reply}
        else:
            call = {"id": f"call{len(self.requests)}", "type": "function", "function": {"name": reply[0], "arguments": json.dumps(reply[1])}}
            message = {"role": "assistant", "content": None, "tool_calls": [call]}
        return httpx.Response(200, json={"choices": [{"message": message}]})


def chat(client: TestClient, text: str = "hello", messages: list[dict] | None = None) -> list[dict]:
    """POST one run and return its events. Every event must be a valid AG-UI event."""
    body = {"threadId": "t", "runId": "r", "state": {}, "tools": [], "context": [], "forwardedProps": {},
            "messages": messages or [{"id": "m1", "role": "user", "content": text}]}
    response = client.post("/api/chat", json=body)
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    lines = [line.removeprefix("data: ") for line in response.text.splitlines() if line.startswith("data: ")]
    for line in lines:
        EVENTS.validate_json(line)
    return [json.loads(line) for line in lines]


def results(events: list[dict]) -> list[str]:
    return [e["content"] for e in events if e["type"] == "TOOL_CALL_RESULT"]


def text(events: list[dict]) -> str:
    return "".join(e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")


@pytest.fixture
def career(tmp_path: Path):
    """A client with Jane's career, a connected mock model, and a function that sets the model's script."""
    box: dict = {}
    transport = httpx.MockTransport(lambda request: box["model"].respond(request))
    with TestClient(create_app(tmp_path, llm_transport=transport)) as client:
        seed_jane(client)
        connect_mock(client)
        ids = {f["title"]: f["id"] for f in client.get("/api/facts").json()}

        def script(*replies: str | tuple[str, dict], **kw) -> Model:
            box["model"] = Model(*replies, **kw)
            return box["model"]

        client.ids, client.script = ids, script  # type: ignore[attr-defined]
        yield client


def test_a_tool_result_goes_to_the_model_and_its_answer_comes_back(career: TestClient) -> None:
    model = career.script(("find_facts", {"query": "kubernetes"}), "You migrated 40 services to Kubernetes.")  # type: ignore[attr-defined]
    events = chat(career, "What did I do with Kubernetes?")
    assert [e["type"] for e in events][0] == "RUN_STARTED" and events[-1]["type"] == "RUN_FINISHED"
    assert "outcome" not in events[-1] or events[-1]["outcome"]["type"] == "success"
    assert text(events) == "You migrated 40 services to Kubernetes."
    found = json.loads(results(events)[0])
    assert {f["title"] for f in found["facts"]} == {"Kubernetes", "Migrated 40 services to Kubernetes"}
    assert "Migrated 40 services" in model.requests[1]["messages"][-1]["content"]  # the second call was sent the tool's reply
    assert model.requests[1]["messages"][-1]["role"] == "tool"


def test_the_model_starts_from_a_short_context_with_each_position_and_its_id(career: TestClient) -> None:
    model = career.script("Hi.")  # type: ignore[attr-defined]
    chat(career)
    system = model.requests[0]["messages"][0]["content"]
    assert "Jane Doe" in system and f"Position {career.ids['Senior Engineer']} | Senior Engineer | Acme Corp | 2019-03 - 2023-01" in system  # type: ignore[attr-defined]


def test_find_facts_filters_by_kind_and_by_words_in_the_attributes(career: TestClient) -> None:
    career.script(("find_facts", {"kind": "Position"}), ("find_facts", {"query": "lisbon"}), "ok")  # type: ignore[attr-defined]
    events = chat(career)
    assert [f["title"] for f in json.loads(results(events)[0])["facts"]] == ["Senior Engineer", "Engineer"]
    assert {f["title"] for f in json.loads(results(events)[1])["facts"]} == {"Jane Doe", "BSc Computer Science", "University of Lisbon"}


def test_get_position_shows_its_organization_and_achievements(career: TestClient) -> None:
    career.script(("get_position", {"fact_id": career.ids["Senior Engineer"]}), "ok")  # type: ignore[attr-defined]
    shown = json.loads(results(chat(career))[0])
    assert shown["organization"] == "Acme Corp"
    assert {a["text"] for a in shown["achievements"]} == {"Cut build times by 60%", "Migrated 40 services to Kubernetes"}


def test_list_skills_and_list_sources(career: TestClient) -> None:
    career.script(("list_skills", {}), ("list_sources", {}), "ok")  # type: ignore[attr-defined]
    skills, sources = (json.loads(r) for r in results(chat(career)))
    assert {s["title"] for s in skills["skills"]} == {"Python", "Kubernetes"}
    assert sources == [{"source": "resume-text", "facts": 12, "status": "ready"}]


def test_get_relationships_shows_each_link_with_the_other_end(career: TestClient) -> None:
    career.script(("get_relationships", {"fact_id": career.ids["Senior Engineer"]}), "ok")  # type: ignore[attr-defined]
    shown = json.loads(results(chat(career))[0])
    links = {(link["kind"], link["direction"], link["other_title"]) for link in shown["links"]}
    assert links == {("HAS_POSITION", "in", "Jane Doe"), ("AT", "out", "Acme Corp"), ("ACHIEVED", "out", "Cut build times by 60%"),
                     ("ACHIEVED", "out", "Migrated 40 services to Kubernetes")}


@pytest.mark.parametrize("call", [("get_position", {"fact_id": "nope"}), ("get_relationships", {"fact_id": "nope"}), ("get_position", {}),
                                  ("find_facts", {"kind": "Hobby"}), ("delete_everything", {})])
def test_a_bad_call_is_a_failed_result_the_model_can_read_not_an_error(career: TestClient, call: tuple[str, dict]) -> None:
    model = career.script(call, "Sorry.")  # type: ignore[attr-defined]
    events = chat(career)
    assert results(events)[0].startswith("Failed:") and text(events) == "Sorry."
    assert model.requests[1]["messages"][-1]["content"].startswith("Failed:")


def test_an_earlier_tool_call_in_the_transcript_is_sent_to_the_model(career: TestClient) -> None:
    model = career.script("Two skills.")  # type: ignore[attr-defined]
    chat(career, messages=[
        {"id": "m1", "role": "user", "content": "List my skills"},
        {"id": "m2", "role": "assistant", "toolCalls": [{"id": "c1", "type": "function", "function": {"name": "list_skills", "arguments": "{}"}}]},
        {"id": "m3", "role": "tool", "toolCallId": "c1", "content": '{"skills": []}'},
        {"id": "m4", "role": "user", "content": "How many?"},
    ])
    sent = model.requests[0]["messages"][1:]
    assert [m["role"] for m in sent] == ["user", "assistant", "tool", "user"]
    assert sent[1]["tool_calls"][0]["function"]["name"] == "list_skills" and sent[2]["tool_call_id"] == "c1"


def test_a_model_that_keeps_calling_tools_is_stopped_with_a_short_answer(career: TestClient) -> None:
    career.script(("list_skills", {}))  # type: ignore[attr-defined]
    events = chat(career)
    assert "stopped" in text(events) and events[-1]["type"] == "RUN_FINISHED"


def test_a_model_that_is_down_ends_the_stream_with_an_error_event(career: TestClient) -> None:
    career.script("x", status=500)  # type: ignore[attr-defined]
    events = chat(career)
    assert events[-1] == {"type": "RUN_ERROR", "message": "The model server answered with status 500"}


def test_with_no_model_connected_the_stream_says_to_connect_one(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        events = chat(client)
    assert events[-1]["type"] == "RUN_ERROR" and events[-1]["message"] == "Connect a model in Settings to chat about your career."
