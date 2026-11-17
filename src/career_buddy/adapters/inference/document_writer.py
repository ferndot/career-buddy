"""Writing a resume or a cover letter from the facts a document prints, by an LLM, in ONE call that answers the whole document. It goes
through the same LlmProvider as the other steps.

The context is the facts, the posting, the person's directions and the template's section list (user message), and the rules for the
document kind, the template's own instructions and the length (system message). The answer is domain/written.WrittenDocument: the
sections of the template in order, each a list of items citing the facts they rest on. Its output is never trusted: the caller
validates it (domain/written.py) and checks every claim with domain/grounding.py. The prompt lives in prompts/ as a versioned text
file; change the wording there and bump the version in the file name.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel
from redstring import LlmProvider, RedstringError

from career_buddy.adapters.inference.errors import unavailable
from career_buddy.domain.generation import Brief, BriefFact, Claim, Rejection
from career_buddy.domain.writing_rules import rules_text
from career_buddy.domain.writing_rules import rules_text
from career_buddy.domain.writing_rules import rules_text
from career_buddy.domain.written import WrittenDocument

PROMPT = "document_writer_v7"
_SECTIONS = dict(re.findall(r"^### (\w+)\n(.*?)(?=^### |\Z)", (Path(__file__).parent / "prompts" / f"{PROMPT}.txt").read_text(encoding="utf-8"), re.M | re.S))


class SlotOut(BaseModel):
    text: str
    fact_ids: list[str] = []
    slot: str


class Repaired(BaseModel):
    slots: list[SlotOut] = []


def system_prompt(brief: Brief, repair: bool = False) -> str:
    """The rules, the document kind's section shapes and general rules (`brief.rules`), then what is particular to this template: its section list, its own instructions
    and the resume's length. A repair gets the rules and the repair instructions only."""
    template = [f"Template: write these sections, in this order: {', '.join(brief.sections)}."] if brief.sections else []
    if brief.template_instructions:
        template.append(f"Template instructions: {brief.template_instructions}")
    if brief.kind == "resume":
        template.append(f"Length: this resume is {brief.caps.pages} page{'s' * (brief.caps.pages != 1)} long. At most {brief.caps.bullets} bullets for each position and {brief.caps.skills} skills in all.")
    parts = [_SECTIONS["rules"], *([] if repair else [_SECTIONS[brief.kind], rules_text(brief.rules, brief.kind)]), "\n".join(template), _SECTIONS["repair" if repair else "output"]]
    return "\n".join(p.strip() for p in parts if p.strip())


def _facts(facts: Sequence[BriefFact]) -> dict[str, object]:
    """The facts as the writer reads them: each position with its achievements together, the skills and education as lists. Every id stays."""
    positions: dict[str, dict[str, object]] = {f.id: {"id": f.id, "title": f.text, "started": f.started, "finished": f.finished, "achievements": []} for f in facts if f.kind == "position"}
    for f in facts:
        if f.kind == "achievement":  # a repair may carry an achievement without its position
            positions.setdefault(f.position_id, {"id": f.position_id, "achievements": []})["achievements"].append({"id": f.id, "text": f.text})  # type: ignore[attr-defined]
    summary = next(({"id": f.id, "text": f.text} for f in facts if f.kind == "summary"), None)
    return {**({"summary": summary} if summary else {}), "positions": list(positions.values()),
            "skills": [{"id": f.id, "text": f.text} for f in facts if f.kind == "skill"],
            "education": [{"id": f.id, "text": f.text, "started": f.started, "finished": f.finished} for f in facts if f.kind == "education"]}


def payload(brief: Brief, facts: Sequence[BriefFact], failed: Sequence[Rejection] = ()) -> str:
    """The user message: the context as JSON."""
    out: dict[str, object] = {
        "kind": brief.kind, "sections": list(brief.sections), "company": brief.company, "role": brief.role, "directions": brief.instructions,
        "posting": brief.posting, "job_terms": list(brief.terms), "missing_terms": list(brief.missing), "pinned": sorted(brief.pinned),
        "facts": _facts(facts),
    }
    if failed:
        out["failed"] = [{"slot": r.slot, "text": r.claim.text, "fact_ids": list(r.claim.fact_ids), "reasons": list(r.reasons)} for r in failed]
    return json.dumps(out, indent=1)


def _repair_facts(brief: Brief, failed: Sequence[Rejection]) -> list[BriefFact]:
    """Only the facts the failed texts cite. A text that cited none could draw on anything, so then all of them."""
    if any(not r.claim.fact_ids for r in failed):
        return list(brief.facts)
    cited = {i for r in failed for i in r.claim.fact_ids}
    return [f for f in brief.facts if f.id in cited]


class ProviderDocumentWriter:
    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    async def write(self, brief: Brief) -> WrittenDocument:
        try:
            return await self._provider.extract(payload(brief, brief.facts), WrittenDocument, system_prompt=system_prompt(brief))
        except RedstringError as error:
            raise unavailable(error) from error

    async def repair(self, brief: Brief, failed: Sequence[Rejection]) -> dict[str, Claim]:
        """One new try at the failed slots only. The answer is a claim by slot id, to be checked again."""
        try:
            answer = await self._provider.extract(payload(brief, _repair_facts(brief, failed), failed), Repaired,
                                                  system_prompt=system_prompt(brief, repair=True))
        except RedstringError as error:
            raise unavailable(error) from error
        return {s.slot: Claim(s.text, tuple(s.fact_ids)) for s in answer.slots}
