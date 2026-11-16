"""redstring's LlmProvider over any OpenAI-compatible chat endpoint (llama.cpp, vLLM, Ollama, OpenAI, Gemini)."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from career_buddy.adapters.inference.errors import CAUGHT, unavailable
from career_buddy.adapters.inference.structured import instructions, read_reply, warn_if_cut_off


class StructuredOpenAIProvider:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        """`client` carries the base URL and auth header, so tests can hand it a MockTransport."""
        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def extract[S: BaseModel](self, text: str, schema: type[S], *, system_prompt: str | None = None) -> S:
        try:
            response = await self._client.post(
                "chat/completions",
                json={"model": self._model, "temperature": 0,
                      "messages": [{"role": "system", "content": instructions(system_prompt, schema)},
                                   {"role": "user", "content": text}]},
            )
            response.raise_for_status()
            choice = response.json()["choices"][0]
            content = choice["message"]["content"] or ""
        except CAUGHT as error:
            raise unavailable(error) from error
        warn_if_cut_off(self._model, choice.get("finish_reason"), "length", content)
        return read_reply(content, schema, self._model)
