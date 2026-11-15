"""Native Anthropic Messages API. Not the OpenAI layer: Anthropic calls that beta, and it rejects `temperature: 0`."""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from career_graph.adapters.inference.errors import CAUGHT, unavailable
from career_graph.adapters.inference.openai_compatible import PROMPT, _to_batch
from career_graph.adapters.inference.openai_rewriter import PROMPT as REWRITE_PROMPT
from career_graph.domain.model import FactBatch

ANTHROPIC_URL = "https://api.anthropic.com/v1"
VERSION = "2023-06-01"


def anthropic_client(api_key: str, transport: httpx.AsyncBaseTransport | None = None, base_url: str = ANTHROPIC_URL) -> httpx.AsyncClient:
    # Redirects are not followed (the httpx default), so the key stays with the host it was saved for.
    return httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers={"x-api-key": api_key, "anthropic-version": VERSION},
                             transport=transport, timeout=120)


async def _message(client: httpx.AsyncClient, model: str, system: str, text: str, max_tokens: int) -> str:
    # No `temperature`: current Claude models reject values below 1, and the default is fine here.
    response = await client.post("messages", json={"model": model, "max_tokens": max_tokens, "system": system,
                                                   "messages": [{"role": "user", "content": text}]})
    response.raise_for_status()
    return "".join(block.get("text", "") for block in response.json()["content"] if block.get("type") == "text")


class AnthropicExtractor:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self._client, self._model = client, model

    async def extract(self, text: str, source: str) -> FactBatch:
        try:
            reply = await _message(self._client, self._model, PROMPT, text, 4096)
            return _to_batch(json.loads(reply[reply.index("{"): reply.rindex("}") + 1]), source)  # tolerate a code fence
        except CAUGHT as error:
            raise unavailable(error) from error


class AnthropicRewriter:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self._client, self._model = client, model

    async def rewrite(self, text: str, terms: Sequence[str]) -> str:
        system = REWRITE_PROMPT.format(terms=f"\nWhere already true you may stress: {', '.join(terms)}." if terms else "")
        try:
            return (await _message(self._client, self._model, system, text, 512)).strip()
        except CAUGHT as error:
            raise unavailable(error) from error
