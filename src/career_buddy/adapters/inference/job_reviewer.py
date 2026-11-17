"""Reading a job posting for what it requires, by an LLM. It goes through the same LlmProvider as the other steps.

Only the posting is sent: no fact, name or contact detail. The answer is never trusted: the caller runs it through
domain/review.validate. The prompt lives in prompts/ as a versioned text file.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from redstring import LlmProvider, RedstringError

from career_buddy.adapters.inference.errors import unavailable
from career_buddy.domain.review import Review

PROMPT = "job_review_v1"
_SYSTEM = (Path(__file__).parent / "prompts" / f"{PROMPT}.txt").read_text(encoding="utf-8").strip()


class Reviewed(BaseModel):
    title: str = ""
    company: str = ""
    must_have: list[str] = []
    nice_to_have: list[str] = []


class ProviderJobReviewer:
    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    async def review(self, posting: str) -> Review:
        try:
            answer = await self._provider.extract(json.dumps({"posting": posting}), Reviewed, system_prompt=_SYSTEM)
        except RedstringError as error:
            raise unavailable(error) from error
        return Review(answer.title, answer.company, tuple(answer.must_have), tuple(answer.nice_to_have))
