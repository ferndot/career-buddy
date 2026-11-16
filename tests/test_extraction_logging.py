"""Why an extraction came back thin must be readable from the log, and a reply that is not an extraction must not pass as an empty one."""

import asyncio
import json
import logging

import httpx
import pytest

from career_graph.adapters.inference.redstring_extractor import RedstringExtractor
from career_graph.adapters.inference.structured_anthropic import StructuredAnthropicProvider, anthropic_client
from career_graph.adapters.inference.structured_openai import StructuredOpenAIProvider
from career_graph.application.ports import LLMUnavailable
from career_graph.domain.model import FactKind

LOG = "career_graph.extraction"
RESUME = "Ada Lovelace\n" + "Engineer at Acme 2019-2021. Built things.\n" * 150  # long enough for several chunks


def ent(name: str, kind: str) -> dict:
    return {"name": name, "entity_type": kind}


def openai_extractor(content: str, finish: str = "stop") -> RedstringExtractor:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]}))
    client = httpx.AsyncClient(base_url="http://llm.test/v1/", transport=transport)
    return RedstringExtractor(StructuredOpenAIProvider(client, "mock-model"))


def extract(extractor: RedstringExtractor, text: str = RESUME):
    return asyncio.run(extractor.extract(text, "resume.txt"))


def test_a_reply_of_the_wrong_shape_is_an_error_not_an_empty_extraction(caplog) -> None:
    caplog.set_level(logging.INFO, LOG)
    with pytest.raises(LLMUnavailable):
        extract(openai_extractor(json.dumps({"positions": [{"title": "Engineer"}]})))
    warning = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert "missing entities, relationships" in warning and "positions" in warning  # the cause and a preview of the reply


def test_entity_types_are_matched_ignoring_case() -> None:
    batch = extract(openai_extractor(json.dumps({
        "entities": [ent("Ada", "person"), ent("Engineer at Acme", "position"), ent("Acme", "ORGANIZATION"), ent("Python", " Skill ")],
        "relationships": [{"source_name": "Engineer at Acme", "target_name": "Acme", "relationship_type": "at"}],
    })))
    assert {f.kind for f in batch.facts} == {FactKind.PERSON, FactKind.POSITION, FactKind.ORGANIZATION, FactKind.SKILL}


def test_the_log_says_what_each_chunk_returned_and_what_was_dropped(caplog) -> None:
    caplog.set_level(logging.INFO, LOG)
    extract(openai_extractor(json.dumps({"entities": [ent("Ada", "Person"), ent("Acme", "Company")], "relationships": []})))
    lines = [r.getMessage() for r in caplog.records]
    assert any("extracting resume.txt:" in m and "characters" in m and "mock-model" in m for m in lines)
    assert sum("the model listed 2 entities" in m for m in lines) >= 2  # one line per chunk
    assert any("chunk(s)" in m and "'Person': 1" in m and "'Company': 1" in m for m in lines)
    dropped = next(r for r in caplog.records if "dropped:" in r.getMessage())
    assert dropped.levelno == logging.WARNING and "entity type 'Company'" in dropped.getMessage()


def test_an_empty_answer_leaves_a_trail_that_explains_the_single_placeholder_fact(caplog) -> None:
    caplog.set_level(logging.INFO, LOG)
    batch = extract(openai_extractor(json.dumps({"entities": [], "relationships": []})))
    assert [f.kind for f in batch.facts] == [FactKind.PERSON]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("listed no entities" in m for m in warnings) and any("placeholder person" in m for m in warnings)


def test_a_reply_cut_off_at_the_output_limit_is_logged_for_both_providers(caplog) -> None:
    caplog.set_level(logging.INFO, LOG)
    cut = '{"entities": [{"name": "Ada", "entity_ty'
    with pytest.raises(LLMUnavailable):
        extract(openai_extractor(cut, finish="length"))
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"content": [{"type": "text", "text": cut}], "stop_reason": "max_tokens"}))
    with pytest.raises(LLMUnavailable):
        extract(RedstringExtractor(StructuredAnthropicProvider(anthropic_client("sk-ant-fake", transport), "claude-test")))
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert sum("output limit" in m for m in messages) == 2 and sum("First 300 characters" in m for m in messages) == 2
    assert not any("sk-ant-fake" in m for m in messages)
