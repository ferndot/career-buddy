"""Connection check: list the server's models. Sends no resume text and costs nothing."""

from __future__ import annotations

import httpx


async def probe_anthropic(client: httpx.AsyncClient) -> list[str]:
    response = await client.get("models")
    response.raise_for_status()
    return [m["id"] for m in response.json()["data"]]


async def probe_openai(client: httpx.AsyncClient, model: str = "default") -> list[str]:
    response = await client.get("models")
    if response.status_code == 404:  # some servers have no model list: ask for one token instead
        chat = await client.post("chat/completions", json={"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]})
        chat.raise_for_status()
        return []
    response.raise_for_status()
    return [m["id"] for m in response.json()["data"]]
