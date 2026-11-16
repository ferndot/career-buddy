"""Duplicate candidates, and which of them are certain enough to merge without asking. Pure: nothing here merges anything."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Collection
from difflib import SequenceMatcher
from itertools import combinations

from career_buddy.domain.knowledge import details
from career_buddy.domain.model import Fact, FactBatch, FactKind, LinkKind, is_hidden, normalize
from career_buddy.domain.periods import period_of
from career_buddy.domain.tailoring import STOPWORDS, stem, tokens

THRESHOLD = 0.90
AUTO_MERGE_THRESHOLD = 0.95  # "OpenAI"/"OpenAPI" score 0.923 and stay a suggestion; only legal-suffix and punctuation variants (1.0) merge by themselves
_LEGAL = {"inc", "corp", "corporation", "co", "ltd", "llc", "plc", "gmbh", "sa", "ag"}


def normalize_org(name: str) -> str:
    words = re.sub(r"[^\w\s]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _LEGAL)


def _ratio(a: str, b: str) -> float:
    """All fuzzy scoring lives here (swap for rapidfuzz later). Sorted, because difflib is not symmetric."""
    x, y = sorted((a, b))
    return SequenceMatcher(None, x, y, autojunk=False).ratio()


def _overlap(a: dict[str, str], b: dict[str, str]) -> bool:
    pa, pb = period_of(a), period_of(b)
    return pa is None or pb is None or pa.overlaps(pb)  # unknown dates: may overlap


def merge_candidates(batch: FactBatch) -> list[tuple[str, str, float]]:
    """(id, id, score) pairs, smaller id first, best score first. Run it on the merged view of the facts."""
    facts = {f.id: f for f in batch.facts if not is_hidden(f)}
    of_kind: dict[FactKind, list[Fact]] = defaultdict(list)
    for fact in sorted(facts.values(), key=lambda f: f.id):
        of_kind[fact.kind].append(fact)

    found: list[tuple[str, str, float]] = []
    org_score: dict[tuple[str, str], float] = {}
    for a, b in combinations(of_kind[FactKind.ORGANIZATION], 2):
        na, nb = normalize_org(a.title), normalize_org(b.title)
        if na and nb and (score := _ratio(na, nb)) >= THRESHOLD:
            org_score[a.id, b.id] = score
            found.append((a.id, b.id, score))

    employer = {l.source_id: l.target_id for l in batch.links if l.kind == LinkKind.AT}
    for a, b in combinations(of_kind[FactKind.POSITION], 2):
        oa, ob = employer.get(a.id), employer.get(b.id)
        if not oa or not ob or normalize(a.title) != normalize(b.title) or not _overlap(a.attributes, b.attributes):
            continue
        score = 1.0 if oa == ob else org_score.get(tuple(sorted((oa, ob))), 0.0)
        if score:
            found.append((a.id, b.id, score))
    found += _achievement_candidates(batch, of_kind[FactKind.ACHIEVEMENT])
    return sorted(found, key=lambda c: (-c[2], c[0], c[1]))


ACHIEVEMENT_THRESHOLD = 0.5  # shared content words over all content words; paraphrases of one result score about 0.6
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*")  # a standalone number: "p95" names a metric, it is not 95


def _achievement_candidates(batch: FactBatch, achievements: list[Fact]) -> list[tuple[str, str, float]]:
    """Achievements under the same position (after position merges) whose wording mostly shares content words.

    Two achievements that state different numbers are different results, so they never pair."""
    parent = {l.target_id: l.source_id for l in batch.links if l.kind == LinkKind.ACHIEVED}
    under: dict[str, list[Fact]] = defaultdict(list)
    for fact in achievements:
        if (position := parent.get(fact.id)):
            under[position].append(fact)
    found: list[tuple[str, str, float]] = []
    for group in under.values():
        for a, b in combinations(group, 2):
            if (score := _achievement_similarity(a, b)) >= ACHIEVEMENT_THRESHOLD:
                found.append((a.id, b.id, score))
    return found


def _achievement_similarity(a: Fact, b: Fact) -> float:
    text_a, text_b = details(a), details(b)
    numbers_a, numbers_b = set(_NUMBER.findall(text_a)), set(_NUMBER.findall(text_b))
    if numbers_a and numbers_b and numbers_a != numbers_b:
        return 0.0
    words_a, words_b = _content_words(text_a), _content_words(text_b)
    return len(words_a & words_b) / len(words_a | words_b) if words_a | words_b else 0.0


def _content_words(text: str) -> set[str]:
    return {stem(t.lower()) for t in tokens(text) if t.lower() not in STOPWORDS}


def canonical_of(a: Fact, b: Fact, touched: Collection[str]) -> str:
    """The id a merge of these two keeps: the one the user touched, else the fuller title, else the smaller id. Symmetric."""
    return min((a, b), key=lambda f: (f.id not in touched, -len(f.title), f.id)).id


def auto_merges(
    batch: FactBatch,
    candidates: Collection[tuple[str, str, float]],
    touched: Collection[str],
    dismissed: Collection[frozenset[str]] = (),
) -> list[tuple[str, str]]:
    """(alias, canonical) pairs to merge without asking: a score at or above AUTO_MERGE_THRESHOLD, the same kind,
    neither fact hidden, dismissed or touched by the user, and each fact in at most one pair."""
    by_id = {f.id: f for f in batch.facts}
    taken: set[str] = set()
    out: list[tuple[str, str]] = []
    for a, b, score in candidates:
        if score < AUTO_MERGE_THRESHOLD or a not in by_id or b not in by_id or {a, b} & (taken | set(touched)):
            continue
        fa, fb = by_id[a], by_id[b]
        if fa.kind != fb.kind or is_hidden(fa) or is_hidden(fb) or frozenset((a, b)) in dismissed:
            continue
        keep = canonical_of(fa, fb, touched)
        out.append((b if keep == a else a, keep))
        taken |= {a, b}
    return out
