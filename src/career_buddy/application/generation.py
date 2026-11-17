"""Generating the text of a document: ask the writer once for the whole document, check every claim against the facts, repair what failed once.

The result is a draft, keyed by the slot ids of the saved layout (domain/slots.py). It is not stored. To keep a draft the
caller saves the document with it as generated text.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from typing import Literal

from career_buddy.application.documents import DocumentService, TailorOptions, Tailored
from career_buddy.application.ports import DocumentWriter, LLMUnavailable, MissingInputs
from career_buddy.domain.generation import MAX_POSTING, Brief, Claim, Rejection, brief_facts, caps_for
from career_buddy.domain.grounding import claims_of, ground

NO_MODEL = "No model is set up. Connect one in Settings to generate text."
MAX_REJECTED = 0.3  # more than this share of the written slots rejected after the repair: no draft


class UngroundedDraft(Exception):
    """Too much of what the model wrote did not match the facts, even after the repair. Carries the rejections."""

    def __init__(self, rejected: list[Rejection]) -> None:
        super().__init__("The model's text did not match your facts closely enough. Your last draft is unchanged.")
        self.rejected = rejected


@dataclass(frozen=True)
class Flag:
    """A slot the person should look at: `not_rewritten` (a bullet shows the fact's own words) or `rejected` (left empty)."""

    code: Literal["not_rewritten", "rejected"]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Draft:
    slots: dict[str, str]  # slot id -> text: `summary`, `bullet:<fact id>`, `skills`, `para:<n>`
    cites: dict[str, list[str]] = field(default_factory=dict)  # slot id -> the fact ids it rests on
    flags: dict[str, Flag] = field(default_factory=dict)


def _brief(t: Tailored, options: TailorOptions, instructions: str, pinned: Collection[str], pages: int, template_instructions: str) -> Brief:
    """What the document prints, as the writer reads it. No name or contact details leave the machine."""
    return Brief(t.spec.kind, brief_facts(t.profile, t.facts, t.absorbed), t.report.matched, t.report.missing,
                 options.inputs.get("company", ""), options.inputs.get("role", ""), instructions,
                 options.job_text.strip()[:MAX_POSTING], caps_for(pages), frozenset(pinned), template_instructions)


class DocumentGeneration:
    def __init__(self, documents: DocumentService, writer: Callable[[], DocumentWriter | None] = lambda: None) -> None:
        self._documents = documents
        self._writer = writer

    async def generate(self, template: str, options: TailorOptions, instructions: str = "",
                       pinned: Collection[str] = (), pages: int = 1, template_instructions: str = "") -> Draft:
        """`pinned` are slot ids the person wrote: the writer leaves them alone. `template_instructions` tell the writer how the template's style reads.

        KeyError: unknown template. MissingInputs: a letter with neither a posting nor a company and role. LLMUnavailable: no model, or it did not
        answer. UngroundedDraft: the model's text failed the facts."""
        t = await self._documents.tailored(template, options)
        if t.spec.kind == "letter" and not options.job_text.strip() and not all(options.inputs.get(k, "").strip() for k in ("company", "role")):
            raise MissingInputs("a job posting: the letter is written for the role and company it names")
        writer = self._writer()  # asked at each request: a model can be connected after start
        if writer is None:
            raise LLMUnavailable(NO_MODEL)
        brief = _brief(t, options, instructions.strip(), pinned, pages, template_instructions.strip())
        skills = t.profile.skills
        protected = [*(x for p in t.profile.positions for x in (p.title, p.organization)),
                     *(x for e in t.profile.education for x in (e.degree, e.school))]
        kept, rejected = ground(brief, claims_of(brief, await writer.write(brief)), skills, protected)
        if rejected:
            kept, rejected = await self._repaired(writer, brief, kept, rejected, skills, protected)
        written = [slot for slot in kept if slot != "skills"]
        if not written or len(rejected) > MAX_REJECTED * (len(written) + len(rejected)):
            raise UngroundedDraft(rejected)
        titles = {aid: text for p in t.profile.positions for aid, text in zip(p.achievement_ids, p.achievements)}
        slots = {slot: claim.text for slot, claim in kept.items()}
        flags = {r.slot: Flag("not_rewritten", r.reasons) if r.slot.startswith("bullet:") else Flag("rejected", r.reasons) for r in rejected}
        for r in rejected:  # a bullet shows the fact's own words, a summary or paragraph stays empty
            slots[r.slot] = titles.get(r.slot.removeprefix("bullet:"), "") if r.slot.startswith("bullet:") else ""
        return Draft(slots, {slot: list(claim.fact_ids) for slot, claim in kept.items()}, flags)

    async def _repaired(self, writer: DocumentWriter, brief: Brief, kept: dict[str, Claim], rejected: list[Rejection], skills: Sequence[str],
                        protected: Sequence[str]) -> tuple[dict[str, Claim], list[Rejection]]:
        """One repair call for the failed slots only. What it does not fix, or does not answer, stays rejected."""
        failed = {r.slot: r for r in rejected}
        try:
            retry = {slot: claim for slot, claim in (await writer.repair(brief, rejected)).items() if slot in failed}
        except LLMUnavailable:
            retry = {}
        fixed, still = ground(brief, retry, skills, protected)
        return {**kept, **fixed}, [r for r in (failed | {r.slot: r for r in still}).values() if r.slot not in fixed]
