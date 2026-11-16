"""One unit test per inference adapter, over httpx.MockTransport: URL, headers, body, error mapping, model list."""

import asyncio
import json

import httpx
import pytest

from career_buddy.adapters.inference.openai_compatible import openai_client
from career_buddy.adapters.inference.probe import probe_anthropic, probe_openai
from career_buddy.adapters.inference.redstring_extractor import RedstringExtractor
from career_buddy.adapters.inference.rewriter import ProviderRewriter
from career_buddy.adapters.inference.structured_anthropic import ANTHROPIC_URL, StructuredAnthropicProvider, anthropic_client
from career_buddy.adapters.inference.structured_openai import StructuredOpenAIProvider
from career_buddy.application.ports import LLMUnavailable

FAKE_KEY = "sk-ant-fake-0000000000000000"
CAREER_JSON = {"name": "Ada Lovelace", "skills": ["Math"], "positions": [
    {"title": "Analyst", "organization": "Royal Society", "achievements": ["Wrote the first algorithm"]}]}  # native Anthropic path
# redstring's extraction shape: entities and relationships by name, typed by the career schema.
EXTRACTED = {
    "entities": [
        {"name": "Ada Lovelace", "entity_type": "Person"},
        {"name": "Analyst", "entity_type": "Position"},
        {"name": "Royal Society", "entity_type": "Organization"},
    ],
    "relationships": [
        {"source_name": "Ada Lovelace", "target_name": "Analyst", "relationship_type": "HAS_POSITION"},
        {"source_name": "Analyst", "target_name": "Royal Society", "relationship_type": "AT"},
    ],
}


def run(coro):
    return asyncio.run(coro)


def seen_by(reply) -> tuple[list[httpx.Request], httpx.MockTransport]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return reply(request)

    return seen, httpx.MockTransport(handler)


def anthropic_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


# --- Anthropic (native Messages API) ---


def test_anthropic_extractor_posts_to_messages_with_native_headers_and_no_temperature() -> None:
    seen, transport = seen_by(lambda r: anthropic_reply("```json\n" + json.dumps(EXTRACTED) + "\n```"))
    extractor = RedstringExtractor(StructuredAnthropicProvider(anthropic_client(FAKE_KEY, transport), "claude-test"))
    batch = run(extractor.extract("my resume", "pasted"))
    (request,) = seen
    assert str(request.url) == ANTHROPIC_URL + "/messages"
    assert request.headers["x-api-key"] == FAKE_KEY
    assert request.headers["anthropic-version"]
    assert "authorization" not in request.headers
    body = json.loads(request.content)
    assert "temperature" not in body
    assert body["model"] == "claude-test" and body["max_tokens"] > 0
    assert body["messages"] == [{"role": "user", "content": "my resume"}] and "JSON Schema" in body["system"]
    assert {f.title for f in batch.facts if f.kind == "Person"} == {"Ada Lovelace"}


def test_anthropic_rewriter_returns_the_text_block_and_maps_errors_without_the_body() -> None:
    seen, transport = seen_by(lambda r: anthropic_reply(json.dumps({"text": "  Authored the first algorithm "})))
    rewriter = ProviderRewriter(StructuredAnthropicProvider(anthropic_client(FAKE_KEY, transport), "claude-test"))
    assert run(rewriter.rewrite("Wrote the first algorithm", ["Python"])) == "Authored the first algorithm"
    assert "Python" in json.loads(seen[0].content)["system"]

    _, failing = seen_by(lambda r: httpx.Response(401, json={"error": {"message": f"bad key {FAKE_KEY}"}}))
    with pytest.raises(LLMUnavailable) as raised:
        run(ProviderRewriter(StructuredAnthropicProvider(anthropic_client(FAKE_KEY, failing), "claude-test")).rewrite("x", []))
    assert "401" in str(raised.value) and FAKE_KEY not in str(raised.value) and "bad key" not in str(raised.value)


def test_anthropic_probe_lists_models_with_a_get_and_no_body() -> None:
    seen, transport = seen_by(lambda r: httpx.Response(200, json={"data": [{"id": "claude-a"}, {"id": "claude-b"}]}))
    assert run(probe_anthropic(anthropic_client(FAKE_KEY, transport))) == ["claude-a", "claude-b"]
    (request,) = seen
    assert request.method == "GET" and str(request.url) == ANTHROPIC_URL + "/models" and request.content == b""


# --- OpenAI-compatible (Gemini, Ollama, LM Studio, llama.cpp, custom) ---


def test_openai_extractor_posts_to_chat_completions_with_bearer_and_maps_errors() -> None:
    reply = lambda r: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(EXTRACTED)}}]})  # noqa: E731
    seen, transport = seen_by(reply)
    client = openai_client("http://llm.test/v1/", FAKE_KEY, transport)
    batch = run(RedstringExtractor(StructuredOpenAIProvider(client, "m")).extract("my resume", "pasted"))
    (request,) = seen
    assert str(request.url) == "http://llm.test/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert json.loads(request.content)["messages"][-1] == {"role": "user", "content": "my resume"}
    assert any(f.title == "Ada Lovelace" for f in batch.facts)

    _, failing = seen_by(lambda r: httpx.Response(500, text=f"boom {FAKE_KEY}"))
    with pytest.raises(LLMUnavailable) as raised:
        run(RedstringExtractor(StructuredOpenAIProvider(openai_client("http://llm.test/v1", FAKE_KEY, failing), "m")).extract("x", "s"))
    assert "500" in str(raised.value) and FAKE_KEY not in str(raised.value)


def test_openai_rewriter_uses_the_client_base_url_and_omits_auth_without_a_key() -> None:
    seen, transport = seen_by(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": '{"text": " Reworded "}'}}]}))
    client = openai_client("http://localhost:9931/v1", "", transport)
    assert run(ProviderRewriter(StructuredOpenAIProvider(client, "m")).rewrite("Original", [])) == "Reworded"
    assert str(seen[0].url) == "http://localhost:9931/v1/chat/completions" and "authorization" not in seen[0].headers


def test_openai_probe_lists_models_and_falls_back_to_a_one_token_chat_on_404() -> None:
    seen, transport = seen_by(lambda r: httpx.Response(200, json={"data": [{"id": "gemma"}]}))
    assert run(probe_openai(openai_client("http://llm.test/v1", FAKE_KEY, transport))) == ["gemma"]
    assert seen[0].method == "GET" and str(seen[0].url) == "http://llm.test/v1/models" and seen[0].content == b""

    def no_models(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    seen, transport = seen_by(no_models)
    assert run(probe_openai(openai_client("http://llm.test/v1", "", transport), "my-model")) == []
    chat = json.loads(seen[1].content)
    assert seen[1].method == "POST" and chat["max_tokens"] == 1 and chat["model"] == "my-model"
