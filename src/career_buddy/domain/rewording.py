"""Gate for LLM rewording (plan-v2, "Optional LLM rewording"). Pure: a candidate may not add facts."""

from __future__ import annotations

import re
from collections.abc import Iterable

from career_buddy.domain.document import Origin
from career_buddy.domain.markers import clean
from career_buddy.domain.strictness import GROWTH
from career_buddy.domain.tailoring import grams, stem, is_tech, tokens

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def specifics(source: str, candidate: str, skills: Iterable[str], protected: Iterable[str] = (), missing: Iterable[str] = ()) -> list[str]:
    """Reasons a candidate states a specific the source does not: a number, a new name or tool, a job term the profile lacks, a lost
    title, employer or degree. The same at every strictness level."""
    reasons: list[str] = []
    if extra := set(_NUMBER.findall(candidate)) - set(_NUMBER.findall(source)):
        reasons.append(f"number not in the source: {', '.join(sorted(extra))}")

    known = {stem(t) for text in (source, *skills) for t in tokens(text)}
    # The first word is capitalized anyway, so only later capitalized or tech-shaped words count as names.
    names = [t for i, t in enumerate(tokens(candidate)) if i and (t[0].isupper() or is_tech(t))]
    if new := [t for t in names if stem(t) not in known]:
        reasons.append(f"new term not in the source or profile skills: {', '.join(new)}")

    have = grams(candidate) - grams(source)
    if added := [m for m in missing if " ".join(map(stem, m.split())) in have]:
        reasons.append(f"missing job term added: {', '.join(added)}")
    if lost := [p for p in protected if p.lower() in source.lower() and p.lower() not in candidate.lower()]:
        reasons.append(f"protected text changed: {', '.join(lost)}")
    return reasons


def wording(source: str, candidate: str, strictness: str = "strict") -> list[str]:
    """Reasons the wording strays: a banned marker, or more length than the level allows over the source."""
    reasons: list[str] = []
    # Flags are weak signals for the user to see, not grounds to reject. Only text clean() would have to change counts.
    if markers := [c for c in clean(candidate, Origin.SUGGESTION)[1] if c.kind != "flag"]:
        reasons.append(f"banned marker: {markers[0].found}")
    limit = GROWTH[strictness].bullet
    if len(candidate) > limit * len(source):
        reasons.append(f"too long: more than {limit:g} times the source")
    return reasons


def verify_rewording(
    source: str,
    candidate: str,
    skills: Iterable[str],
    protected: Iterable[str] = (),
    missing: Iterable[str] = (),
    strictness: str = "strict",
) -> list[str]:
    """Reasons to reject the candidate. Empty means it only rewords the source.

    `protected` are titles, organizations and degrees that must survive if the source has them. `missing` are job
    terms the profile lacks, which must never appear. `strictness` (domain/strictness.py) loosens the wording check only.
    """
    return specifics(source, candidate, skills, protected, missing) + wording(source, candidate, strictness)
