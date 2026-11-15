"""Gate for LLM rewording (plan-v2, "Optional LLM rewording"). Pure: a candidate may not add facts."""

from __future__ import annotations

import re
from collections.abc import Iterable

from career_graph.domain.document import Origin
from career_graph.domain.markers import clean
from career_graph.domain.tailoring import grams, stem, is_tech, tokens

MAX_GROWTH = 1.3
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def verify_rewording(
    source: str,
    candidate: str,
    skills: Iterable[str],
    protected: Iterable[str] = (),
    missing: Iterable[str] = (),
) -> list[str]:
    """Reasons to reject the candidate. Empty means it only rewords the source.

    `protected` are titles, organizations and degrees that must survive if the source has them. `missing` are job
    terms the profile lacks, which must never appear.
    """
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

    # Flags are weak signals for the user to see, not grounds to reject. Only text clean() would have to change counts.
    if markers := [c for c in clean(candidate, Origin.SUGGESTION)[1] if c.kind != "flag"]:
        reasons.append(f"banned marker: {markers[0].found}")
    if len(candidate) > MAX_GROWTH * len(source):
        reasons.append("too long: more than 1.3 times the source")
    if lost := [p for p in protected if p.lower() in source.lower() and p.lower() not in candidate.lower()]:
        reasons.append(f"protected text changed: {', '.join(lost)}")
    return reasons
