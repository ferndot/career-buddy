"""Assembles a read model (Profile) from facts and links, and ranks it against a job posting."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

from career_graph.domain.model import Fact, FactBatch, FactKind, LinkKind, is_hidden


@dataclass(frozen=True)
class PositionView:
    title: str
    organization: str
    attributes: dict[str, str] = field(default_factory=dict)
    achievements: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    id: str = ""
    achievement_ids: tuple[str, ...] = ()  # parallel to achievements
    organization_id: str = ""


@dataclass(frozen=True)
class EducationView:
    school: str
    degree: str
    attributes: dict[str, str] = field(default_factory=dict)
    id: str = ""
    school_id: str = ""  # the organization fact; empty when the school is only an attribute

    @property
    def label(self) -> str:
        return ", ".join(dict.fromkeys(part for part in (self.degree, self.school) if part))


@dataclass(frozen=True)
class Profile:
    name: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    positions: tuple[PositionView, ...] = ()
    education: tuple[EducationView, ...] = ()
    skills: tuple[str, ...] = ()
    id: str = ""
    skill_ids: tuple[str, ...] = ()  # parallel to skills


def _order(fact: Fact) -> float:
    """attributes.order as a number; bullets without a usable one sort after the ordered ones."""
    try:
        return int(fact.attributes["order"])
    except (KeyError, ValueError):
        return math.inf


def assemble_profile(batch: FactBatch) -> Profile:
    """Hidden facts are left out."""
    facts = {f.id: f for f in batch.facts if not is_hidden(f)}
    edges: dict[tuple[str, LinkKind], list[str]] = defaultdict(list)
    for link in batch.links:
        edges[(link.source_id, link.kind)].append(link.target_id)

    def targets(source_id: str, kind: LinkKind) -> list[Fact]:
        return [facts[t] for t in edges.get((source_id, kind), []) if t in facts]

    people = [f for f in facts.values() if f.kind == FactKind.PERSON]
    if not people:
        return Profile(skills=tuple(sorted({f.title for f in facts.values() if f.kind == FactKind.SKILL})))
    person = people[0]

    positions = []
    for pos in targets(person.id, LinkKind.HAS_POSITION):
        orgs = targets(pos.id, LinkKind.AT)
        achievements = sorted(targets(pos.id, LinkKind.ACHIEVED), key=_order)  # stable: unordered keep import order
        positions.append(
            PositionView(
                title=pos.title,
                organization=orgs[0].title if orgs else "",
                attributes=pos.attributes,
                achievements=tuple(f.title for f in achievements),
                skills=tuple(f.title for f in targets(pos.id, LinkKind.USES_SKILL)),
                id=pos.id,
                achievement_ids=tuple(f.id for f in achievements),
                organization_id=orgs[0].id if orgs else "",
            )
        )

    education = []
    for edu in targets(person.id, LinkKind.HAS_EDUCATION):
        schools = targets(edu.id, LinkKind.ATTENDED)
        school = schools[0].title if schools else edu.attributes.get("school", "")
        education.append(EducationView(school, edu.title, edu.attributes, edu.id, schools[0].id if schools else ""))

    skills = targets(person.id, LinkKind.HAS_SKILL)
    return Profile(person.title, person.attributes, tuple(positions), tuple(education),
                   tuple(f.title for f in skills), person.id, tuple(f.id for f in skills))


_WORD = re.compile(r"[a-z0-9+#.]+")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def rank_for_job(profile: Profile, job_text: str) -> tuple[list[PositionView], list[str]]:
    """Positions ordered by overlap with the job text, and the profile skills the job mentions."""
    wanted = _words(job_text)

    def score(pos: PositionView) -> int:
        return len(wanted & _words(" ".join([pos.title, *pos.achievements, *pos.skills])))

    ranked = sorted(profile.positions, key=score, reverse=True)
    matched = [s for s in profile.skills if _words(s) & wanted]
    return ranked, matched
