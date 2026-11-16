"""Writing one bullet from an achievement's facts. It is inference, so it goes through the same LlmProvider as extraction."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from redstring import LlmProvider, RedstringError

from career_graph.adapters.inference.errors import unavailable

PROMPT = """Write one resume bullet about the accomplishment in these facts, worded to be as effective as possible for
the job posting below. Lead with the action, then the result, in the terms that job's reader looks for. Copy the facts'
own wording if it is already the most effective; otherwise write new wording. Keep every number, name, tool, skill, job
title, employer, date and degree exactly as given, and add none. Put the bullet in the "text" field.{job}{terms}"""


class Reworded(BaseModel):
    text: str


class ProviderRewriter:
    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    async def rewrite(self, text: str, terms: Sequence[str], job_text: str = "") -> str:
        """`text` is the achievement's knowledge (see domain/knowledge.py), not a bullet to polish."""
        job = f"\n\nJob posting:\n{job_text.strip()}" if job_text.strip() else ""
        stress = f"\nWhere already true you may stress: {', '.join(terms)}." if terms else ""
        system = PROMPT.format(job=job, terms=stress)
        try:
            answer = await self._provider.extract(text, Reworded, system_prompt=system)
        except RedstringError as error:
            raise unavailable(error) from error
        return answer.text.strip()
