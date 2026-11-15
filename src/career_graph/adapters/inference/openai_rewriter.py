"""LLM rewording of one bullet via any OpenAI-compatible chat endpoint."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from career_graph.application.ports import LLMUnavailable

PROMPT = """Reword one resume bullet in plain words. Keep every fact. Do not add or change numbers, names, tools,
skills, job titles, employers, dates or degrees. Reply with the reworded bullet only.{terms}"""


class OpenAICompatibleRewriter:
    """`client` carries the base URL (and any auth header), so tests can hand it a MockTransport."""

    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self._client = client
        self._model = model

    async def rewrite(self, text: str, terms: Sequence[str]) -> str:
        system = PROMPT.format(
            terms=f"\nWhere already true you may stress: {', '.join(terms)}." if terms else "",
        )
        try:
            response = await self._client.post(
                "chat/completions",
                json={"model": self._model, "temperature": 0.2,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
            raise LLMUnavailable(str(error)) from error
