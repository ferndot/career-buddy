"""The general writing rules a person can replace (Settings > Writing): GET, PUT and reset over HTTP, validation, and what the writer is told."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.domain.writing_rules import LETTER_RULES, RESUME_RULES
from career_buddy.web.app import create_app
from test_generate_api import LETTER, RESUME, Model, open_client

URL = "/api/writing/rules"


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def test_defaults_until_a_person_saves_their_own(client: TestClient) -> None:
    body = client.get(URL).json()
    assert body["resume"] == {"rules": list(RESUME_RULES), "default": list(RESUME_RULES), "custom": False}
    assert body["letter"]["rules"] == list(LETTER_RULES)


def test_saved_rules_are_returned_and_survive_a_restart(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as c:
        saved = c.put(f"{URL}/letter", json={"rules": ["  Be brief. ", "No jokes."]}).json()
        assert saved == {"rules": ["Be brief.", "No jokes."], "default": list(LETTER_RULES), "custom": True}
        assert c.get(URL).json()["resume"]["custom"] is False
    with TestClient(create_app(tmp_path)) as again:
        assert again.get(URL).json()["letter"]["rules"] == ["Be brief.", "No jokes."]


def test_an_empty_list_or_a_reset_returns_to_the_default(client: TestClient) -> None:
    client.put(f"{URL}/resume", json={"rules": ["One"]})
    assert client.put(f"{URL}/resume", json={"rules": []}).json()["rules"] == list(RESUME_RULES)
    client.put(f"{URL}/resume", json={"rules": ["One"]})
    assert client.delete(f"{URL}/resume").status_code == 204
    assert client.get(URL).json()["resume"]["custom"] is False


@pytest.mark.parametrize("rules", [[""], ["   "], ["x" * 301], ["ok"] * 21, "text", [1]])
def test_invalid_rules_are_refused_and_nothing_is_saved(client: TestClient, rules) -> None:
    assert client.put(f"{URL}/resume", json={"rules": rules}).status_code == 422
    assert client.get(URL).json()["resume"]["custom"] is False


def test_limits_are_inclusive_and_the_kind_is_checked(client: TestClient) -> None:
    assert client.put(f"{URL}/resume", json={"rules": ["x" * 300] * 20}).status_code == 200
    assert client.put(f"{URL}/cv", json={"rules": ["a"]}).status_code == 422
    assert client.delete(f"{URL}/cv").status_code == 422


def written_rules(tmp_path: Path, body: dict, setup=lambda c: None) -> str:
    """The system prompt of the writer's first call."""
    model = Model(write=lambda p: {"sections": []})
    c = open_client(tmp_path, model)
    try:
        setup(c)
        c.post("/api/documents/generate", json=body)
    finally:
        c.__exit__(None, None, None)
    return model.systems[0]


def test_the_writer_is_told_the_saved_rules_in_place_of_the_default(tmp_path: Path) -> None:
    system = written_rules(tmp_path, RESUME, lambda c: c.put(f"{URL}/resume", json={"rules": ["Use only nouns."]}))
    assert "- Use only nouns." in system
    assert RESUME_RULES[0] not in system


def test_the_writer_falls_back_to_the_default_and_other_kinds_are_untouched(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert RESUME_RULES[0] in written_rules(tmp_path / "a", RESUME)
    system = written_rules(tmp_path / "b", LETTER, lambda c: c.put(f"{URL}/resume", json={"rules": ["Use only nouns."]}))
    assert LETTER_RULES[0] in system and "Use only nouns." not in system
