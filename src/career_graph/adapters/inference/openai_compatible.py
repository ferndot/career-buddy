"""OpenAI-compatible client and the shared career-JSON mapping. Extraction itself runs through redstring (redstring_extractor)."""

from __future__ import annotations

import httpx

from career_graph.domain.builder import BatchBuilder
from career_graph.domain.model import FactBatch

PROMPT = """Extract a career history from the user's text. Reply with JSON only, shaped:
{"name": str, "headline": str, "skills": [str],
 "positions": [{"title": str, "organization": str, "period": str, "achievements": [str], "skills": [str]}],
 "education": [{"school": str, "degree": str, "period": str}]}
Use only facts stated in the text. Achievements are concrete accomplishments, not duties."""


def openai_client(base_url: str, api_key: str = "", transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """A client rooted at the server's base URL. The key goes in a header, never the URL. Redirects are not followed."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers=headers, transport=transport, timeout=120)


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
