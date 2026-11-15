"""Model-backed extraction via any OpenAI-compatible chat endpoint (llama.cpp, vLLM, Ollama, OpenAI)."""

from __future__ import annotations

import json

import httpx

from career_graph.domain.builder import BatchBuilder
from career_graph.domain.model import FactBatch

PROMPT = """Extract a career history from the user's text. Reply with JSON only, shaped:
{"name": str, "headline": str, "skills": [str],
 "positions": [{"title": str, "organization": str, "period": str, "achievements": [str], "skills": [str]}],
 "education": [{"school": str, "degree": str, "period": str}]}
Use only facts stated in the text. Achievements are concrete accomplishments, not duties."""


class OpenAICompatibleExtractor:
    def __init__(self, base_url: str, model: str, api_key: str = "none", client: httpx.AsyncClient | None = None):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.AsyncClient(timeout=120)

    async def extract(self, text: str, source: str) -> FactBatch:
        response = await self._client.post(
            self._url,
            headers=self._headers,
            json={
                "model": self._model,
                "temperature": 0,
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
            },
        )
        response.raise_for_status()
        data = json.loads(response.json()["choices"][0]["message"]["content"])
        return _to_batch(data, source)


def _to_batch(data: dict, source: str) -> FactBatch:
    b = BatchBuilder(source)
    person = b.person(data.get("name") or "Me", headline=data.get("headline", ""))
    for name in data.get("skills", []):
        b.skill(person, name)
    for pos in data.get("positions", []):
        b.position(
            person,
            pos.get("title", ""),
            pos.get("organization", ""),
            achievements=tuple(pos.get("achievements", [])),
            skills=tuple(pos.get("skills", [])),
            period=pos.get("period", ""),
        )
    for edu in data.get("education", []):
        b.education(person, edu.get("school", ""), edu.get("degree", ""), period=edu.get("period", ""))
    return b.build()
