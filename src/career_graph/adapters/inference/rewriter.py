"""Rewording one bullet. It is inference, so it goes through the same LlmProvider as extraction."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from redstring import LlmProvider, RedstringError

from career_graph.adapters.inference.errors import unavailable

PROMPT = """Reword one resume bullet in plain words. Keep every fact. Do not add or change numbers, names, tools,
skills, job titles, employers, dates or degrees. Put the reworded bullet in the "text" field.{terms}"""


class Reworded(BaseModel):
    text: str


class ProviderRewriter:
    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    async def rewrite(self, text: str, terms: Sequence[str]) -> str:
        system = PROMPT.format(terms=f"\nWhere already true you may stress: {', '.join(terms)}." if terms else "")
        try:
            answer = await self._provider.extract(text, Reworded, system_prompt=system)
        except RedstringError as error:
            raise unavailable(error) from error
        return answer.text.strip()
