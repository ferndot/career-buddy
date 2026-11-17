"""Gate for generated text: every claim must cite the brief's facts and may not say more than they do. Pure.

`claims_of` takes the claims of a validated written document (domain/written.py), one per text the writer wrote. `ground` then
checks each claim. A bullet or an education line goes through `verify_rewording`, as suggested rewordings do, against the
achievements or education entries it cites. A summary, a skills line or a paragraph is prose that several facts make up, so it
gets `verify_prose`: the same checks on numbers, new names and job terms the profile lacks, without the bullet's length cap and
without counting a capitalised word at the start of a sentence as a name.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from career_buddy.domain.document import Origin
from career_buddy.domain.generation import Brief, Claim, Rejection
from career_buddy.domain.markers import clean
from career_buddy.domain.rewording import verify_rewording
from career_buddy.domain.tailoring import TOKEN_PATTERN, grams, is_tech, stem, tokens
from career_buddy.domain.written import WrittenDocument, nodes

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MAX_PROSE_GROWTH = 6  # times the cited facts' length, plus PROSE_ALLOWANCE: prose links facts together
PROSE_ALLOWANCE = 300


def _starts_sentence(text: str, at: int) -> bool:
    before = text[:at].rstrip()
    return not before or before[-1] in ".!?:\n"


_LABEL = re.compile(r"\b[\w&/ -]{1,30}:\s*")  # "Languages: " in front of a list of skills


def verify_prose(source: str, candidate: str, known: Iterable[str] = (), missing: Iterable[str] = (), sentences: bool = True) -> list[str]:
    """Reasons to reject a candidate paragraph. `known` is wording the source need not contain: the company, the role, skills.
    With `sentences` False every capitalised word counts as a name, as in a list of skills, where each entry starts a "sentence"."""
    reasons: list[str] = []
    if extra := set(_NUMBER.findall(candidate)) - set(_NUMBER.findall(source)):
        reasons.append(f"number not in the source: {', '.join(sorted(extra))}")
    seen = {stem(t) for text in (source, *known) for t in tokens(text)} | {"i"}
    names = [m[0] for m in TOKEN_PATTERN.finditer(candidate)
             if (is_tech(m[0]) or (m[0][0].isupper() and not (sentences and _starts_sentence(candidate, m.start())))) and stem(m[0]) not in seen]
    if names:
        reasons.append(f"new term not in the source: {', '.join(names)}")
    have = grams(candidate) - grams(source)
    if added := [m for m in missing if " ".join(map(stem, m.split())) in have]:
        reasons.append(f"missing job term added: {', '.join(added)}")
    if len(candidate) > MAX_PROSE_GROWTH * len(source) + PROSE_ALLOWANCE:
        reasons.append("too long for the facts it cites")
    return reasons


def claims_of(brief: Brief, doc: WrittenDocument) -> dict[str, Claim]:
    """The writer's claims by slot id. A slot the person pinned has no text and no claim: it is theirs, not the writer's."""
    return {slot: Claim(text, ids) for slot, text, ids in nodes(doc) if text and slot not in brief.pinned}


def ground(
    brief: Brief,
    claims: Mapping[str, Claim],
    skills: Iterable[str] = (),
    protected: Iterable[str] = (),
) -> tuple[dict[str, Claim], list[Rejection]]:
    """The claims that pass, by slot id, and why the others do not.

    A cited id that is not in the brief is dropped from the claim; a claim left with no cited fact is rejected. Text is
    cleaned as a suggestion first, so a banned marker is removed, not a reason."""
    texts = {f.id: f.text for f in brief.facts}
    kinds = {f.id: f.kind for f in brief.facts}
    skills = list(skills)
    known = [brief.company, brief.role, *skills]
    kept: dict[str, Claim] = {}
    rejected: list[Rejection] = []
    for slot, claim in claims.items():
        text = clean(claim.text, Origin.SUGGESTION)[0].strip()
        ids = tuple(dict.fromkeys(i for i in claim.fact_ids if i in texts))
        if not text:
            reasons = ["empty"]
        elif not ids:
            reasons = ["cites no fact"]
        elif slot.startswith(("bullet:", "edu:")):  # what a line rests on: the achievements or education entries it cites, not the skills it names
            source = [texts[i] for i in ids if kinds[i] in ("achievement", "education")]
            reasons = verify_rewording("\n".join(source), text, skills, protected, brief.missing) if source else ["cites no achievement"]
        elif slot.startswith("skills"):  # the names a line lists must be the skills it cites; a label such as "Languages:" is free
            reasons = verify_prose("\n".join(texts[i] for i in ids), _LABEL.sub("", text), known, brief.missing, sentences=False)
        else:
            reasons = verify_prose("\n".join(texts[i] for i in ids), text, known, [m for m in brief.missing if m.lower() not in f"{brief.company} {brief.role}".lower()])  # the posting's own company and role may be named
        if reasons:
            rejected.append(Rejection(slot, tuple(reasons), Claim(text, ids)))
        else:
            kept[slot] = Claim(text, ids)
    return kept, rejected
