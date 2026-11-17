"""The review of a job posting: what it asks for, checked against the posting itself. Pure.

A model reads the posting and lists requirements. Its list is never trusted: `validate` keeps only terms the posting really
contains and drops what is not a requirement (the company, the title, a generic word, a fragment). `uncovered` then tells
which of them no career fact says.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from career_buddy.domain.profile import Profile
from career_buddy.domain.tailoring import STOPWORDS, stem, tokens

MAX_MUST, MAX_NICE = 12, 8
# Words a posting is full of that name no skill. Plain data; the tailoring STOPWORDS apply as well.
GENERIC = frozenset(
    """policy policies applications application ecosystem ecosystems mission impact sciences science enterprise enterprises
    business customers customer people culture benefits opportunity opportunities growth environment solutions products product
    services service industry organization organizations world global technology technologies skills skill knowledge""".split()
)


@dataclass(frozen=True)
class Review:
    title: str = ""
    company: str = ""
    must_have: tuple[str, ...] = ()
    nice_to_have: tuple[str, ...] = ()


def _plain(text: str) -> str:
    return " ".join(text.replace("’", "'").lower().split())


def _bare(text: str) -> str:
    """Lower case without a possessive, so the company and "Anthropic's" are one name."""
    return re.sub(r"'s$", "", _plain(text))


def _contains(posting: str, plain: str) -> bool:
    """As a whole word or phrase: "Java" is not in "JavaScript"."""
    return re.search(rf"(?<![a-z0-9+#]){re.escape(plain)}(?![a-z0-9+#])", posting) is not None


def _is_requirement(term: str, posting: str, names: set[str]) -> bool:
    plain = _plain(term)
    return (len(plain) >= 2 and any(c.isalpha() for c in plain) and _contains(posting, plain) and _bare(term) not in names
            and not (len(plain.split()) == 1 and (plain in STOPWORDS | GENERIC or stem(plain) in STOPWORDS | GENERIC)))


def _kept(terms: Iterable[str], posting: str, names: set[str], seen: set[str], cap: int) -> tuple[str, ...]:
    out: list[str] = []
    for term in terms:
        term = " ".join(term.split())
        if len(out) < cap and _plain(term) not in seen and _is_requirement(term, posting, names):
            seen.add(_plain(term))
            out.append(term)
    return tuple(out)


def validate(raw: Review, posting: str) -> Review:
    """What the model said, minus every term the posting does not contain or that is not a requirement.

    Terms keep the model's order and spelling. A term listed as must-have is not repeated as nice-to-have."""
    text = _plain(posting)
    title, company = (" ".join(x.split()) if _plain(x) in text else "" for x in (raw.title, raw.company))
    names = {_bare(x) for x in (title, company) if x}
    seen: set[str] = set()
    must = _kept(raw.must_have, text, names, seen, MAX_MUST)
    return Review(title, company, must, _kept(raw.nice_to_have, text, names, seen, MAX_NICE))


def fact_text(profile: Profile) -> list[str]:
    """Everything the facts say that a requirement could be met by."""
    return [*profile.attributes.values(), *profile.skills, *(e.label for e in profile.education),
            *(t for p in profile.positions for t in (p.title, *p.achievements, *p.skills))]


def _significant(text: str) -> set[str]:
    return {stem(t) for t in tokens(text) if t.lower() not in STOPWORDS and any(c.isalpha() for c in t)}


def uncovered(terms: Iterable[str], facts: Iterable[str]) -> tuple[str, ...]:
    """The terms some of whose meaningful words no fact uses. "5+ years of Python" is covered by a Python skill."""
    have: set[str] = set()
    for text in facts:
        have |= _significant(text)
    return tuple(t for t in terms if not _significant(t) <= have)
