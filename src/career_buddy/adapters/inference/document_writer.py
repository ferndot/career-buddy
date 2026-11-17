"""Writing a resume or a cover letter from the facts a document prints, by an LLM. It goes through the same LlmProvider as the other steps.

Its output is never trusted: the caller checks every claim with domain/grounding.py. The prompt lives in prompts/ as a
versioned text file; change the wording there and bump the version in the file name.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel
from redstring import LlmProvider, RedstringError

from career_buddy.adapters.inference.errors import unavailable
from career_buddy.domain.generation import Brief, BriefFact, Bullet, Claim, Generated, Rejection

PROMPT = "document_writer_v4"
_SECTIONS = dict(re.findall(r"^### (\w+)\n(.*?)(?=^### |\Z)", (Path(__file__).parent / "prompts" / f"{PROMPT}.txt").read_text(encoding="utf-8"), re.M | re.S))


class Cited(BaseModel):
    text: str
    fact_ids: list[str] = []


class BulletOut(BaseModel):
    fact_id: str
    text: str


class Written(BaseModel):
    summary: Cited | None = None
    bullets: list[BulletOut] = []
    skill_ids: list[str] = []
    paragraphs: list[Cited] = []


class SlotOut(Cited):
    slot: str


class Repaired(BaseModel):
    slots: list[SlotOut] = []


def system_prompt(section: str, repair: bool = False) -> str:
    """The rules, the section's own instructions (summary, experience, skills or letter) and, for a repair, how to repair."""
    return "\n".join(s.strip() for s in (_SECTIONS["rules"], _SECTIONS[section], *([_SECTIONS["repair"]] if repair else [])))


def _fact(f: BriefFact) -> dict[str, str]:
    return {"id": f.id, "kind": f.kind, "text": f.text, "position_id": f.position_id, "started": f.started, "finished": f.finished}


def payload(brief: Brief, facts: Sequence[BriefFact], failed: Sequence[Rejection] = ()) -> str:
    out: dict[str, object] = {
        "kind": brief.kind, "section": brief.section, "company": brief.company, "role": brief.role, "directions": brief.instructions, "posting": brief.posting,
        "job_terms": list(brief.terms), "missing_terms": list(brief.missing), "pinned": sorted(brief.pinned), "facts": [_fact(f) for f in facts],
    }
    if brief.template_instructions:
        out["template_instructions"] = brief.template_instructions
    if brief.kind == "resume":
        out["caps"] = {"pages": brief.caps.pages, "bullets_per_position": brief.caps.bullets, "skills": brief.caps.skills}
    if failed:
        out["failed"] = [{"slot": r.slot, "text": r.claim.text, "fact_ids": list(r.claim.fact_ids), "reasons": list(r.reasons)} for r in failed]
    return json.dumps(out)


def _repair_facts(brief: Brief, failed: Sequence[Rejection]) -> list[BriefFact]:
    """Only the facts the failed texts cite. A text that cited none could draw on anything, so then all of them."""
    if any(not r.claim.fact_ids for r in failed):
        return list(brief.facts)
    cited = {i for r in failed for i in r.claim.fact_ids}
    return [f for f in brief.facts if f.id in cited]


class ProviderDocumentWriter:
    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    async def write(self, brief: Brief) -> Generated:
        try:
            answer = await self._provider.extract(payload(brief, brief.facts), Written, system_prompt=system_prompt(brief.section))
        except RedstringError as error:
            raise unavailable(error) from error
        return Generated(
            Claim(answer.summary.text, tuple(answer.summary.fact_ids)) if answer.summary else None,
            tuple(Bullet(b.fact_id, b.text) for b in answer.bullets),
            tuple(answer.skill_ids),
            tuple(Claim(p.text, tuple(p.fact_ids)) for p in answer.paragraphs),
        )

    async def repair(self, brief: Brief, failed: Sequence[Rejection]) -> dict[str, Claim]:
        """One new try at the failed slots only. The answer is a claim by slot id, to be checked again."""
        try:
            answer = await self._provider.extract(payload(brief, _repair_facts(brief, failed), failed), Repaired,
                                                  system_prompt=system_prompt(brief.section, repair=True))
        except RedstringError as error:
            raise unavailable(error) from error
        return {s.slot: Claim(s.text, tuple(s.fact_ids)) for s in answer.slots}
