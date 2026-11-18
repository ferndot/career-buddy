"""Would this draft get the interview? A few plain checks against the posting, the critic for the revise step. Pure; no model judges.

The posting's terms the facts cover (`Brief.terms`) should show in the text: across the document (`TOP_TERMS` of them; half used is enough),
in the summary, and in the first bullets, where a reader decides whether to go on. The coverage issues of domain/coverage.py (a relevant
role missing or thin) count against the score. Below `PASS` the draft gets one `weak_fit` issue that names what to fix and which
slots may be rewritten to fix it. Terms the facts do not cover are never suggested: grounding forbids writing them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from career_buddy.domain.coverage import Issue
from career_buddy.domain.generation import Brief
from career_buddy.domain.tailoring import grams, stem

TOP_TERMS = 10  # the posting's first terms that count towards the share
LEAD_BULLETS = 3  # the bullets a reader sees first
PASS = 0.7  # a score under this asks for a revision
FLAG_PENALTY = 0.2  # per coverage issue


def _hits(terms: Sequence[str], text: str) -> list[str]:
    have = grams(text)
    return [t for t in terms if " ".join(map(stem, t.split())) in have]


def fit(brief: Brief, kept: Mapping[str, str], found: Sequence[Issue] = ()) -> tuple[float, Issue | None]:
    """The score (0 to 1) of the grounded texts by slot, in reading order, and a `weak_fit` issue when it is under PASS.
    The checks that apply are averaged: the share of terms used, the summary, the lead bullets; each coverage issue takes FLAG_PENALTY off."""
    terms = [t for t in brief.terms if t.strip()][:TOP_TERMS]
    if not terms:
        return 1.0, None
    used = set(_hits(terms, " ".join(kept.values())))
    parts = [min(1.0, len(used) / (len(terms) / 2))]  # using half of them is full marks: a document cannot carry every term
    reasons: list[str] = []
    slots: list[str] = []
    for slot, label in (("summary", "the summary"),):
        if slot in kept:
            ok = bool(_hits(terms, kept[slot]))
            parts.append(float(ok))
            if not ok:
                reasons.append(f"{label} names none of the posting's terms")
                slots.append(slot)
    lead = [s for s in kept if s.startswith("bullet:")][:LEAD_BULLETS]
    if lead:
        ok = any(_hits(terms, kept[s]) for s in lead)
        parts.append(float(ok))
        if not ok:
            reasons.append(f"none of the first {len(lead)} bullets shows a posting term")
            slots.append(lead[0])
    score = max(0.0, sum(parts) / len(parts) - FLAG_PENALTY * sum(i.code in ("missing_position", "thin_position") for i in found))
    if score >= PASS:
        return score, None
    unused = [t for t in terms if t not in used]
    if unused:
        reasons.append(f"posting terms the facts support but the text lacks: {', '.join(unused)}")
    text = (f"This draft fits the posting weakly (score {score:.2f} of 1): {'; '.join(reasons) or 'too few of its terms show'}. Put the most relevant proof "
            "first, in the posting's words, only where the facts support it. A text you may rewrite is named in `slots`.")
    return score, Issue("weak_fit", text, slots=tuple(slots))
