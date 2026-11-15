"""Helpers that point an app at a mocked LLM through the public LLM connections API."""

from __future__ import annotations


def connect_mock(http, base_url: str = "http://llm.test/v1") -> str:
    """Save a keyless custom connection and make it the active one. `http` is a TestClient or httpx.Client."""
    created = http.post("/api/llm/connections", json={"preset": "custom", "label": "Mock", "base_url": base_url, "model": "mock-model"})
    assert created.status_code == 201, created.text
    conn_id = created.json()["id"]
    assert http.put("/api/llm/active", json={"id": conn_id}).status_code == 200
    return conn_id
