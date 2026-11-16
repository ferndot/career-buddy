"""redstring's LlmProvider over Anthropic's native Messages API. Not the OpenAI layer: Anthropic rejects `temperature: 0`."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from career_graph.adapters.inference.errors import CAUGHT, unavailable
from career_graph.adapters.inference.structured import instructions, read_reply

ANTHROPIC_URL = "https://api.anthropic.com/v1"
VERSION = "2023-06-01"


def anthropic_client(api_key: str, transport: httpx.AsyncBaseTransport | None = None, base_url: str = ANTHROPIC_URL) -> httpx.AsyncClient:
    # Redirects are not followed (the httpx default), so the key stays with the host it was saved for.
    return httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers={"x-api-key": api_key, "anthropic-version": VERSION},
                             transport=transport, timeout=120)


class StructuredAnthropicProvider:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def extract[S: BaseModel](self, text: str, schema: type[S], *, system_prompt: str | None = None) -> S:
        try:
            response = await self._client.post(
                "messages",
                json={"model": self._model, "max_tokens": 4096, "system": instructions(system_prompt, schema),
                      "messages": [{"role": "user", "content": text}]},
            )
            response.raise_for_status()
            reply = "".join(b.get("text", "") for b in response.json()["content"] if b.get("type") == "text")
        except CAUGHT as error:
            raise unavailable(error) from error
        return read_reply(reply, schema, self._model)
