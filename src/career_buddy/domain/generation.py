"""Writing a document from facts: what goes to a writer. Pure.

A writer (an LLM) is sent the facts, the posting, the person's directions and the template's section list, and writes the
whole document as sections of items (domain/written.py). Every text names the facts it comes from. The writer is sent
exactly the facts the document prints: every fact the person can see. A hidden fact is not in the brief and so cannot be
in the output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from career_buddy.domain.knowledge import knowledge
from career_buddy.domain.model import Fact
from career_buddy.domain.profile import Profile
from career_buddy.domain.strictness import DEFAULT, Strictness

MAX_POSTING = 6000  # characters of the job posting a writer reads
Kind = Literal["summary", "position", "achievement", "skill", "education"]


@dataclass(frozen=True)
class BriefFact:
    id: str
    kind: Kind
    text: str  # an achievement's knowledge text (its title and result); for the others the plain words
    position_id: str = ""  # an achievement's position
    started: str = ""  # when the position (or the education) began and ended, as the person wrote it
    finished: str = ""


@dataclass(frozen=True)
class Caps:
    """How much a resume may hold, from the person's Resume length setting."""

    pages: int
    skills: int  # most skills it lists


ResumeLength = Literal["default", 1]  # "default": the writer picks the length from the general rules, up to two pages; 1: exactly one page
ONE_PAGE, UP_TO_TWO_PAGES = Caps(1, 10), Caps(2, 15)


def caps_for(length: object) -> Caps:
    """A document saved when 2 and 3 pages were offered keeps its stored value: anything but 1 reads as the default."""
    return ONE_PAGE if length == 1 else UP_TO_TWO_PAGES


@dataclass(frozen=True)
class Brief:
    """Everything a writer gets. It holds no name or contact details."""

    kind: Literal["resume", "letter"]
    facts: tuple[BriefFact, ...]
    terms: tuple[str, ...] = ()  # job terms the facts cover
    missing: tuple[str, ...] = ()  # job terms no fact covers: never to be written
    company: str = ""
    role: str = ""
    instructions: str = ""  # the user's free-text directions: tone, length, what to stress
    posting: str = ""  # the job posting, cut to MAX_POSTING
    caps: Caps = ONE_PAGE
    pinned: frozenset[str] = frozenset()  # slot ids the user wrote themselves: their text replaces the writer's
    template_instructions: str = ""  # how the chosen template and style want the text written
    sections: tuple[str, ...] = ()  # the section keys to write, in order: a resume's summary, experience, ..., or a letter's `body`
    rules: tuple[str, ...] = ()  # the general rules for this kind of document (domain/writing_rules.py): style and selection, never grounding
    strictness: Strictness = DEFAULT  # how loosely the wording may follow the facts (domain/strictness.py); specifics stay strict


@dataclass(frozen=True)
class Claim:
    text: str
    fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rejection:
    """A claim that did not pass the facts, and why. `claim` is what the writer wrote, for the repair call."""

    slot: str
    reasons: tuple[str, ...]
    claim: Claim = Claim("")


def brief_facts(profile: Profile, facts: Mapping[str, Fact], absorbed: Mapping[str, Sequence[Fact]]) -> tuple[BriefFact, ...]:
    """The facts of a profile as a writer reads them. `profile` is what the document prints: hidden facts are not in it."""
    out = [BriefFact(profile.id, "summary", profile.attributes["summary"])] if profile.id and profile.attributes.get("summary") else []
    for pos in profile.positions:
        when = {"started": pos.attributes.get("started", ""), "finished": pos.attributes.get("finished", "")}
        out.append(BriefFact(pos.id, "position", f"{pos.title} at {pos.organization}" if pos.organization else pos.title, **when))
        for aid, text in zip(pos.achievement_ids, pos.achievements):
            out.append(BriefFact(aid, "achievement", knowledge(facts[aid], absorbed.get(aid, ())) if aid in facts else text, pos.id, **when))
    out += [BriefFact(i, "skill", title) for i, title in zip(profile.skill_ids, profile.skills)]
    out += [BriefFact(e.id, "education", e.label, started=e.attributes.get("started", ""), finished=e.attributes.get("finished", ""))
            for e in profile.education if e.id]
    return tuple(f for f in out if f.id)
