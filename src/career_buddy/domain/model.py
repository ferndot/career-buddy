"""Career facts and the typed links between them. Pure: no I/O, no frameworks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class FactKind(StrEnum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    POSITION = "Position"
    ACHIEVEMENT = "Achievement"
    SKILL = "Skill"
    EDUCATION = "Education"


class LinkKind(StrEnum):
    HAS_POSITION = "HAS_POSITION"
    HAS_EDUCATION = "HAS_EDUCATION"
    HAS_SKILL = "HAS_SKILL"
    AT = "AT"  # position -> organization
    ACHIEVED = "ACHIEVED"  # position -> achievement
    USES_SKILL = "USES_SKILL"  # position -> skill
    ATTENDED = "ATTENDED"  # education -> organization


@dataclass(frozen=True)
class Fact:
    id: str
    kind: FactKind
    title: str
    attributes: dict[str, str] = field(default_factory=dict)
    source: str = ""


@dataclass(frozen=True)
class Link:
    source_id: str
    target_id: str
    kind: LinkKind


@dataclass(frozen=True)
class FactBatch:
    facts: tuple[Fact, ...] = ()
    links: tuple[Link, ...] = ()


def is_hidden(fact: Fact) -> bool:
    return fact.attributes.get("hidden") == "true"


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def fact_id(kind: FactKind, title: str, scope: str = "") -> str:
    """Deterministic id, so re-importing the same claim is a no-op."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{kind}|{normalize(title)}|{normalize(scope)}"))


class InvalidFact(ValueError):
    """An edit that the fact model does not allow."""
