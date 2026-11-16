"""Builds a FactBatch from structured claims. Shared by every source and inference adapter."""

from __future__ import annotations

from career_buddy.domain.dates import with_dates
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind, fact_id


class BatchBuilder:
    def __init__(self, source: str) -> None:
        self._source = source
        self._facts: dict[str, Fact] = {}
        self._links: dict[Link, None] = {}

    def _add(self, kind: FactKind, title: str, scope: str = "", **attrs: str) -> str:
        fid = fact_id(kind, title, scope)
        clean = with_dates({key: value.strip() for key, value in attrs.items() if value and value.strip()})
        self._facts.setdefault(fid, Fact(fid, kind, title.strip(), clean, self._source))
        return fid

    def _link(self, source_id: str, target_id: str, kind: LinkKind) -> None:
        self._links[Link(source_id, target_id, kind)] = None

    def person(self, name: str, **attrs: str) -> str:
        return self._add(FactKind.PERSON, name, **attrs)

    def position(
        self,
        person_id: str,
        title: str,
        organization: str,
        *,
        achievements: tuple[str, ...] = (),
        skills: tuple[str, ...] = (),
        **attrs: str,
    ) -> str:
        org_id = self._add(FactKind.ORGANIZATION, organization)
        pos_id = self._add(FactKind.POSITION, title, scope=organization, **attrs)
        self._link(person_id, pos_id, LinkKind.HAS_POSITION)
        self._link(pos_id, org_id, LinkKind.AT)
        for text in achievements:
            ach_id = self._add(FactKind.ACHIEVEMENT, text, scope=f"{title}|{organization}")
            self._link(pos_id, ach_id, LinkKind.ACHIEVED)
        for name in skills:
            self.skill(person_id, name, position_id=pos_id)
        return pos_id

    def skill(self, person_id: str, name: str, position_id: str | None = None) -> str:
        skill_id = self._add(FactKind.SKILL, name)
        self._link(person_id, skill_id, LinkKind.HAS_SKILL)
        if position_id:
            self._link(position_id, skill_id, LinkKind.USES_SKILL)
        return skill_id

    def education(self, person_id: str, school: str, degree: str = "", **attrs: str) -> str:
        edu_id = self._add(FactKind.EDUCATION, degree or school, scope=school, school=school, **attrs)
        school_id = self._add(FactKind.ORGANIZATION, school)
        self._link(person_id, edu_id, LinkKind.HAS_EDUCATION)
        self._link(edu_id, school_id, LinkKind.ATTENDED)
        return edu_id

    def build(self) -> FactBatch:
        return FactBatch(tuple(self._facts.values()), tuple(self._links))
