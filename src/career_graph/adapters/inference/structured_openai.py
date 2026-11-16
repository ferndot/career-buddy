"""redstring's LlmProvider over any OpenAI-compatible chat endpoint (llama.cpp, vLLM, Ollama, OpenAI, Gemini).

The model is asked for one JSON object; the answer is validated against the requested pydantic schema, and a
failure raises redstring's MalformedCompletionError so nothing partial reaches the graph."""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, ValidationError
from redstring import MalformedCompletionError

from career_graph.adapters.inference.errors import CAUGHT, unavailable


class StructuredOpenAIProvider:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        """`client` carries the base URL and auth header, so tests can hand it a MockTransport."""
        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def extract[S: BaseModel](self, text: str, schema: type[S], *, system_prompt: str | None = None) -> S:
        instructions = f"{system_prompt or ''}\n\nReply with one JSON object that matches this JSON Schema, and nothing else:\n"
        instructions += json.dumps(schema.model_json_schema())
        try:
            response = await self._client.post(
                "chat/completions",
                json={
                    "model": self._model,
                    "temperature": 0,
                    "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": text}],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"] or ""
        except CAUGHT as error:
            raise unavailable(error) from error
        try:
            return schema.model_validate_json(content[content.index("{"): content.rindex("}") + 1])  # tolerate a code fence
        except (ValidationError, ValueError) as error:
            raise MalformedCompletionError(model=self._model, schema=schema.__name__, cause=type(error).__name__) from error
