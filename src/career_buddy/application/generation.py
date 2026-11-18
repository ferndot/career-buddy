"""Generating the text of a document: the writer submits the whole document, every claim is checked against the facts, and the writer revises what failed once.

The result is a draft: the written sections (domain/written.py), each text with the slot id of the saved layout (domain/slots.py).
It is not stored. To keep a draft the caller saves the document with its sections.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Collection
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

from career_buddy.application.documents import DocumentService, TailorOptions, Tailored
from career_buddy.application.ports import DocumentWriter, LLMUnavailable, MissingInputs, PageCounter
from career_buddy.domain.coverage import Checked, Pages, issues
from career_buddy.domain.document import Style
from career_buddy.domain.fit import fit
from career_buddy.domain.generation import MAX_POSTING, Brief, Claim, ResumeLength, Rejection, brief_facts, caps_for
from career_buddy.domain.grounding import claims_of, ground
from career_buddy.domain.strictness import DEFAULT, Strictness
from career_buddy.domain.templates import position_heading
from career_buddy.domain.writing_rules import DEFAULT_RULES
from career_buddy.domain.written import LETTER, Item, WrittenDocument, mapped, merged, numbered, texts, validated

log = logging.getLogger(__name__)
NO_MODEL = "No model is set up. Connect one in Settings to generate text."
MAX_REJECTED = 0.3  # more than this share of the written slots rejected after the repair: no draft


class UngroundedDraft(Exception):
    """Too much of what the model wrote did not match the facts, even after the repair. Carries the rejections."""

    def __init__(self, rejected: list[Rejection]) -> None:
        super().__init__("The model's text did not match your facts closely enough. Your last draft is unchanged.")
        self.rejected = rejected


@dataclass(frozen=True)
class Flag:
    """A slot the person should look at: `not_rewritten` (a bullet or education line shows the fact's own words) or `rejected` (left out)."""

    code: Literal["not_rewritten", "rejected"]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Draft:
    """The written document, with a flag for each slot the person should look at. `labels` are the section titles by key, `headings` the
    position headings by position id: the facts' words, not the writer's."""

    doc: WrittenDocument
    flags: dict[str, Flag] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    headings: dict[str, str] = field(default_factory=dict)
    pages: Pages | None = None  # how a resume printed, when it could be measured
    limit: int = 1  # the pages it may take

    def json(self) -> dict[str, object]:
        """The wire form: `sections` (each text with its slot id and the facts it cites, so the document can be shown, edited by slot and saved
        as it is), `slots` (slot -> text of every written text) and `flags`."""
        def node(i: Item) -> dict[str, object]:
            return {"slot": i.slot, "text": i.text, "fact_ids": list(i.fact_ids)}

        def item(i: Item) -> dict[str, object]:
            return {**node(i), "position_id": i.position_id, "heading": self.headings.get(i.position_id, ""), "also": list(i.also),
                    "also_headings": [self.headings.get(p, "") for p in i.also], "bullets": [node(b) for b in i.bullets]}  # type: ignore[arg-type]

        sections = [{"key": s.key, "title": self.labels.get(s.key, ""), "items": [item(i) for i in s.items]} for s in numbered(self.doc).sections]
        return {"sections": sections, "slots": texts(self.doc), "flags": {k: asdict(f) for k, f in self.flags.items()},
                "pages": {"count": self.pages.count, "limit": self.limit} if self.pages else None}


def _brief(t: Tailored, rules: tuple[str, ...], options: TailorOptions, instructions: str, pinned: Collection[str], pages: ResumeLength, template_instructions: str, strictness: Strictness = DEFAULT) -> Brief:
    """What the document prints, as the writer reads it. No name or contact details leave the machine."""
    keys = tuple(k for k, _ in t.spec.sections) if t.spec.kind == "resume" else (LETTER,)
    return Brief(t.spec.kind, brief_facts(t.profile, t.facts, t.absorbed), t.report.matched, t.report.missing,
                 options.inputs.get("company", ""), options.inputs.get("role", ""), instructions,
                 options.job_text.strip()[:MAX_POSTING], caps_for(pages), frozenset(pinned), template_instructions, keys, rules, strictness)


class DocumentGeneration:
    def __init__(self, documents: DocumentService, writer: Callable[[], DocumentWriter | None] = lambda: None,
                 rules: Callable[[str], tuple[str, ...]] = lambda kind: DEFAULT_RULES[kind],  # type: ignore[index]
                 pages: PageCounter | None = None, strictness: Callable[[], Strictness] = lambda: DEFAULT) -> None:
        self._documents = documents
        self._pages = pages  # None: the length is not checked
        self._writer = writer
        self._rules = rules  # read at each request: Settings can change them
        self._strictness = strictness  # likewise

    async def generate(self, template: str, options: TailorOptions, instructions: str = "",
                       pinned: Collection[str] = (), pages: ResumeLength = "default", template_instructions: str = "", style: Style = Style()) -> Draft:
        """`pinned` are slot ids the person wrote: the writer's text for one is replaced by theirs, and one the writer left out is added. `template_instructions` tell the writer how the template's style reads. `style` is what the length is measured in.

        KeyError: unknown template. MissingInputs: a letter with neither a posting nor a company and role. LLMUnavailable: no model, or it did not
        answer. UngroundedDraft: the model's text failed the facts."""
        t = await self._documents.tailored(template, options)
        if t.spec.kind == "letter" and not options.job_text.strip() and not all(options.inputs.get(k, "").strip() for k in ("company", "role")):
            raise MissingInputs("a job posting: the letter is written for the role and company it names")
        writer = self._writer()  # asked at each request: a model can be connected after start
        if writer is None:
            raise LLMUnavailable(NO_MODEL)
        brief = _brief(t, self._rules(t.spec.kind), options, instructions.strip(), pinned, pages, template_instructions.strip(), self._strictness())
        skills = t.profile.skills
        protected = [*(x for p in t.profile.positions for x in (p.title, p.organization)),
                     *(x for e in t.profile.education for x in (e.degree, e.school))]

        own = {aid: text for p in t.profile.positions for aid, text in zip(p.achievement_ids, p.achievements)} | {e.id: e.label for e in t.profile.education}

        def printed(doc: WrittenDocument, kept: dict[str, Claim], rejected: list[Rejection]) -> WrittenDocument:
            """The document as it prints: grounded text for a kept slot; for a failed one a bullet or education line shows the fact's own words, anything
            else stays empty; a slot the person wrote is blank, their words come with the saved layout."""
            failed = {r.slot for r in rejected}

            def final(slot: str, text: str, ids: tuple[str, ...]) -> tuple[str, tuple[str, ...]] | None:
                if slot in kept:
                    return kept[slot].text, kept[slot].fact_ids
                if slot in failed:
                    return (own.get(ids[0], ""), ids[:1]) if slot.startswith(("bullet:", "edu:")) else ("", ids)
                return text, ids

            return mapped(doc, final)

        async def measured(doc: WrittenDocument, kept: dict[str, Claim], rejected: list[Rejection]) -> Pages | None:
            """One render of the document as it prints. A resume only; never fails the generation: no browser or no page count means no length check."""
            if brief.kind != "resume" or self._pages is None:
                return None
            try:
                composed, _ = await self._documents.compose(template, options, written=printed(doc, kept, rejected))
                return await asyncio.to_thread(self._pages.pages, composed, style)
            except Exception as error:  # noqa: BLE001 - the check is a help
                log.info("Length check skipped: %s", type(error).__name__)
                return None

        async def accept(previous: Checked | None, submitted: WrittenDocument) -> Checked:
            """What the writer submitted, checked. A revision changes only the slots rejected before (accepted text stays), adds what is new, and
            drops bullets it leaves out only when the last render was too long."""
            doc = validated(brief, submitted)
            if previous:
                over = any(i.code == "too_long" for i in previous.issues)
                doc = validated(brief, merged(previous.doc, doc, {r.slot for r in previous.rejected} | {s for i in previous.issues for s in i.slots}, over))
            kept, rejected = ground(brief, claims_of(brief, doc), skills, protected)
            pages = await measured(doc, kept, rejected)
            found = issues(brief, doc, pages, date.today().year)
            weak = fit(brief, {slot: c.text for slot, c in kept.items()}, found)[1]
            return Checked(doc, kept, rejected, pages, (*found, *([weak] if weak else [])))

        checked = await writer.write(brief, accept)
        written, kept, rejected = checked.doc, checked.kept, checked.rejected
        counted = [slot for slot in kept if not slot.startswith("skills")]
        weighed = [r for r in rejected if not r.slot.startswith("skills")]  # a skills line is a list, not a claim about the work: it never sinks a draft
        if not counted or len(weighed) > MAX_REJECTED * (len(counted) + len(weighed)):
            raise UngroundedDraft(rejected)
        flags = {r.slot: Flag("not_rewritten" if r.slot.startswith(("bullet:", "edu:")) else "rejected", r.reasons) for r in rejected}
        return Draft(printed(written, kept, rejected), flags, dict(t.spec.sections), {p.id: position_heading(p) for p in t.profile.positions}, checked.pages, brief.caps.pages)
