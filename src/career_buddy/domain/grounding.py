"""Gate for generated text: every claim must cite the brief's facts and may not say more than they do. Pure.

`claims_of` takes what the writer wrote and drops what was never the writer's to write. `ground` then checks each claim.
Bullets go through `verify_rewording`, as suggested rewordings do. A summary or a paragraph is prose that several facts
make up, so it gets `verify_prose`: the same checks on numbers, new names and job terms the profile lacks, without the
bullet's length cap and without counting a capitalised word at the start of a sentence as a name.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping

from career_buddy.domain.document import Origin
from career_buddy.domain.generation import Brief, Claim, Generated, Rejection
from career_buddy.domain.markers import clean
from career_buddy.domain.rewording import verify_rewording
from career_buddy.domain.tailoring import TOKEN_PATTERN, grams, is_tech, stem, tokens

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MAX_PROSE_GROWTH = 6  # times the cited facts' length, plus PROSE_ALLOWANCE: prose links facts together
PROSE_ALLOWANCE = 300


def _starts_sentence(text: str, at: int) -> bool:
    before = text[:at].rstrip()
    return not before or before[-1] in ".!?:\n"


def verify_prose(source: str, candidate: str, known: Iterable[str] = (), missing: Iterable[str] = ()) -> list[str]:
    """Reasons to reject a candidate paragraph. `known` is wording the source need not contain: the company, the role, skills."""
    reasons: list[str] = []
    if extra := set(_NUMBER.findall(candidate)) - set(_NUMBER.findall(source)):
        reasons.append(f"number not in the source: {', '.join(sorted(extra))}")
    seen = {stem(t) for text in (source, *known) for t in tokens(text)} | {"i"}
    names = [m[0] for m in TOKEN_PATTERN.finditer(candidate)
             if (is_tech(m[0]) or (m[0][0].isupper() and not _starts_sentence(candidate, m.start()))) and stem(m[0]) not in seen]
    if names:
        reasons.append(f"new term not in the source: {', '.join(names)}")
    have = grams(candidate) - grams(source)
    if added := [m for m in missing if " ".join(map(stem, m.split())) in have]:
        reasons.append(f"missing job term added: {', '.join(added)}")
    if len(candidate) > MAX_PROSE_GROWTH * len(source) + PROSE_ALLOWANCE:
        reasons.append("too long for the facts it cites")
    return reasons


def claims_of(brief: Brief, written: Generated) -> dict[str, Claim]:
    """What the writer wrote, by slot id (`summary`, `bullet:<fact id>`, `para:<n>`, `skills`), for the brief's kind only.

    Dropped without a word, since the writer cannot fix them: a slot the person pinned, a bullet for a fact that is not one of
    the brief's achievements, a second text for the same bullet, bullets over the per-position cap, skills the brief lacks or over the cap."""
    out: dict[str, Claim] = {}
    if brief.kind == "letter":
        return {f"para:{n}": c for n, c in enumerate(written.paragraphs, 1) if f"para:{n}" not in brief.pinned}
    if written.summary and "summary" not in brief.pinned:
        out["summary"] = written.summary
    position = {f.id: f.position_id for f in brief.facts if f.kind == "achievement"}
    used: Counter[str] = Counter()
    for item in written.bullets:
        slot = f"bullet:{item.fact_id}"
        if item.fact_id in position and slot not in out and slot not in brief.pinned and used[position[item.fact_id]] < brief.caps.bullets:
            used[position[item.fact_id]] += 1
            out[slot] = Claim(item.text, (item.fact_id,))
    names = {f.id: f.text for f in brief.facts if f.kind == "skill"}
    ids = tuple(dict.fromkeys(i for i in written.skill_ids if i in names))[: brief.caps.skills]
    if ids and "skills" not in brief.pinned:
        out["skills"] = Claim(", ".join(names[i] for i in ids), ids)
    return out


def ground(
    brief: Brief,
    claims: Mapping[str, Claim],
    skills: Iterable[str] = (),
    protected: Iterable[str] = (),
) -> tuple[dict[str, Claim], list[Rejection]]:
    """The claims that pass, by slot id, and why the others do not.

    A cited id that is not in the brief is dropped from the claim; a claim left with no cited fact is rejected. Text is
    cleaned as a suggestion first, so a banned marker is removed, not a reason. The skills list is the facts' own names."""
    texts = {f.id: f.text for f in brief.facts}
    skills = list(skills)
    known = [brief.company, brief.role, *skills]
    kept: dict[str, Claim] = {}
    rejected: list[Rejection] = []
    for slot, claim in claims.items():
        text = clean(claim.text, Origin.SUGGESTION)[0].strip()
        ids = tuple(dict.fromkeys(i for i in claim.fact_ids if i in texts))
        if slot == "skills":
            kept[slot] = claim
            continue
        if not text:
            reasons = ["empty"]
        elif not ids:
            reasons = ["cites no fact"]
        elif slot.startswith("bullet:"):
            reasons = verify_rewording(texts[ids[0]], text, skills, protected, brief.missing)
        else:
            reasons = verify_prose("\n".join(texts[i] for i in ids), text, known, [m for m in brief.missing if m.lower() not in f"{brief.company} {brief.role}".lower()])  # the posting's own company and role may be named
        if reasons:
            rejected.append(Rejection(slot, tuple(reasons), Claim(text, ids)))
        else:
            kept[slot] = Claim(text, ids)
    return kept, rejected
