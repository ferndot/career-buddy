"""Tailoring (plan-v2, "Tailoring"): pick and order what the profile already says for one job. Pure.

Nothing is invented. Bullets and skills are only selected and reordered, the summary is kept verbatim, and terms the
profile lacks are reported as missing for the user to add if true.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace

from career_buddy.domain.dates import parse
from career_buddy.domain.document import Document, Entry, Line, Origin
from career_buddy.domain.profile import PositionView, Profile
from career_buddy.domain.templates import TemplateSpec

# Generic English plus the filler of job postings. Plain data: extend freely.
STOPWORDS = frozenset(
    """a an and are as at be been but by can do does for from had has have he her his i if in into is it its me my no
    not of on or our out she so than that the their them then there these they this to up us was we were what when
    which who will with would you your about also any all each more most other some such very able across ability
    experience experienced work working works team teams role roles job company years year strong including
    looking join must should well new using use used within etc requirement requirements qualification
    qualifications preferred plus responsibilities responsibility""".split()
)
_TOKEN = re.compile(r"[A-Za-z0-9+#]+(?:[.'’][A-Za-z0-9+#]+)*")
# shortcut: a requirements section is a line matching this up to the next blank line, not a real parser.
_REQUIREMENTS = re.compile(r"requirement|qualification|must have|you have|you.ll need|what you bring", re.I)
TOKEN_PATTERN = _TOKEN
REPORT_LIMIT = 25


@dataclass(frozen=True)
class Term:
    key: str  # stemmed, what text is matched against
    label: str  # what the report shows
    weight: float


@dataclass(frozen=True)
class Report:
    matched: tuple[str, ...] = ()  # job terms in what is printed
    missing: tuple[str, ...] = ()  # job terms nowhere in the profile: add only if true


def stem(token: str) -> str:
    low = token.lower()
    return low[:-1] if len(low) > 3 and low.endswith("s") and not low.endswith("ss") else low


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def grams(text: str) -> set[str]:
    stems = [stem(t) for t in tokens(text)]
    return {*stems, *(f"{a} {b}" for a, b in zip(stems, stems[1:]))}


def is_tech(token: str) -> bool:
    return bool(re.search(r"\d|[+#]|\w\.\w|[a-z][A-Z]", token)) or (len(token) > 1 and token.isupper())


def job_terms(job_text: str) -> list[Term]:
    """Tokens and bigrams without stopwords, in order of first appearance, each with a weight."""
    seen: dict[str, dict] = {}

    def note(key: str, label: str, cap: bool, tech: bool, req: bool) -> None:
        s = seen.setdefault(key, {"label": label, "n": 0, "cap": False, "tech": False, "req": False})
        s["n"] += 1
        s["cap"] |= cap
        s["tech"] |= tech
        s["req"] |= req

    in_requirements = False
    for line in job_text.splitlines():
        if not line.strip():
            in_requirements = False
            continue
        in_requirements |= bool(_REQUIREMENTS.search(line))
        toks = tokens(line)
        ok = [t.lower() not in STOPWORDS and len(t) > 1 and any(c.isalpha() for c in t) for t in toks]
        cap = [i > 0 and t[0].isupper() for i, t in enumerate(toks)]
        for i, tok in enumerate(toks):
            if ok[i]:
                note(stem(tok), tok.lower(), cap[i], is_tech(tok), in_requirements)
            if ok[i] and i + 1 < len(toks) and ok[i + 1]:
                nxt = toks[i + 1]
                note(f"{stem(tok)} {stem(nxt)}", f"{tok.lower()} {nxt.lower()}", cap[i] and cap[i + 1],
                     is_tech(tok) or is_tech(nxt), in_requirements)
    return [
        Term(key, s["label"], 1 + 0.5 * min(s["n"] - 1, 4) + s["cap"] + s["tech"] + s["req"])
        for key, s in seen.items()
    ]


def _weight(terms: list[Term], grams: set[str]) -> float:
    return sum(t.weight for t in terms if t.key in grams)


_MONTHS = {m: n for n, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_OPEN_END = (9999, 12)


def _year_month(text: str) -> tuple[int, int] | None:
    if iso := parse(text):
        return iso[0], iso[1] if len(iso) > 1 else 1
    year = re.search(r"\b(?:19|20)\d{2}\b", text)
    if not year:
        return None
    month = next((_MONTHS[w[:3]] for w in re.findall(r"[a-z]+", text.lower()) if w[:3] in _MONTHS), 1)
    return int(year[0]), month


def _when(pos: PositionView) -> tuple[tuple[int, int], tuple[int, int]]:
    """(end, start) of a position. A missing or open end means it is current."""
    attrs = pos.attributes
    start, end = attrs.get("started", ""), attrs.get("finished", "")
    return _year_month(end) or _OPEN_END, _year_month(start) or (0, 0)


def _pick(pos: PositionView, terms: list[Term], limit: int, selection: frozenset[str] | None) -> PositionView:
    base = _weight(terms, grams(" ".join([pos.title, *pos.skills])))
    ids = pos.achievement_ids or ("",) * len(pos.achievements)
    items = [(base + _weight(terms, grams(text)), text, aid) for text, aid in zip(pos.achievements, ids)]
    if selection is not None:
        items = [item for item in items if item[2] in selection]
    items.sort(key=lambda item: -item[0])  # stable: ties keep their original order
    if selection is None:
        items = items[: max(1, limit)]
    return replace(pos, achievements=tuple(i[1] for i in items),
                   achievement_ids=tuple(i[2] for i in items) if pos.achievement_ids else ())


def _skills(
    profile: Profile, job_text: str, limit: int, selection: frozenset[str] | None = None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lowered = job_text.lower()
    used = Counter(s.lower() for p in profile.positions for s in set(p.skills))
    ids = profile.skill_ids or ("",) * len(profile.skills)

    def where(skill: str) -> int:
        # shortcut: case-insensitive, so a skill named "Go" matches the word "go". Upgrade if that bites.
        m = re.search(rf"(?<![a-z0-9+#]){re.escape(skill.lower())}(?![a-z0-9+#])", lowered)
        return m.start() if m else -1

    rows = [(where(s), s, i) for s, i in zip(profile.skills, ids)]
    matched = sorted((r for r in rows if r[0] >= 0), key=lambda r: r[0])
    rest = sorted((r for r in rows if r[0] < 0), key=lambda r: -used[r[1].lower()])
    ordered = matched + rest
    chosen = ordered[:limit] if selection is None else [r for r in ordered if r[2] in selection]  # a chosen set is not capped
    return tuple(r[1] for r in chosen), tuple(r[2] for r in chosen) if profile.skill_ids else ()


def _texts(profile: Profile) -> list[str]:
    return [*profile.attributes.values(), *profile.skills,
            *(t for p in profile.positions for t in (p.title, *p.achievements, *p.skills))]


def _report(source: Profile, shown: Profile, terms: list[Term]) -> Report:
    shown_grams = set().union(*map(grams, _texts(shown)))
    have = set().union(*map(grams, _texts(source)))
    ranked = sorted(terms, key=lambda t: -t.weight)
    return Report(tuple(t.label for t in ranked if t.key in shown_grams)[:REPORT_LIMIT],
                  tuple(t.label for t in ranked if t.key not in have)[:REPORT_LIMIT])


def tailor(
    profile: Profile,
    job_text: str,
    spec: TemplateSpec,
    selection: frozenset[str] | None = None,
    skill_selection: frozenset[str] | None = None,
    education_selection: frozenset[str] | None = None,
) -> tuple[Profile, Report]:
    """The profile reduced to what the template shows for this job, and the report.

    `selection` is bullet ids, `skill_selection` skill ids, `education_selection` education ids. None keeps the
    template's own choice; a set keeps exactly those that exist, ignoring the template's caps.
    """
    terms = job_terms(job_text)
    positions = tuple(_pick(p, terms, spec.bullets, selection) for p in sorted(profile.positions, key=_when, reverse=True))
    skills, skill_ids = _skills(profile, job_text, spec.skills, skill_selection)
    education = profile.education if education_selection is None else tuple(e for e in profile.education if e.id in education_selection)
    tailored = replace(profile, positions=positions, education=education, skills=skills, skill_ids=skill_ids)
    return tailored, _report(profile, tailored, terms)


PARAGRAPHS = ("summary", "headline")  # override keys that name a profile paragraph, not a bullet's fact id


def override_paragraphs(profile: Profile, overrides: dict[str, str]) -> Profile:
    """The user's own summary and headline for this document. The stored profile is untouched."""
    own = {key: text.strip() for key in PARAGRAPHS if (text := overrides.get(key, "")).strip()}
    return replace(profile, attributes={**profile.attributes, **own})


def apply_overrides(doc: Document, overrides: dict[str, str]) -> Document:
    """The user's own wording for bullets, by fact id. Headings are never overridden."""

    def bullet(line: Line) -> Line:
        text = overrides.get(line.source_fact_id or "", "").strip()
        return replace(line, text=text, origin=Origin.USER) if text else line

    def entry(item: Entry) -> Entry:
        return replace(item, bullets=tuple(map(bullet, item.bullets)))

    return replace(doc, sections=tuple(replace(s, entries=tuple(map(entry, s.entries))) for s in doc.sections))
