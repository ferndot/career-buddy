"""AI-marker policy (plan-v2, "AI-marker policy"). Pure. Runs at render time only: stored facts are never rewritten.

Two kinds of list. Artifacts are cleanup, not authorship evidence: they are stripped. Everything else is a weak signal
(word frequencies shift in LLM-assisted text, but humans write these words too), so it is flagged or lightly swapped,
never used to reject text. Words with no source are not listed at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from career_graph.domain.document import Document, Entry, Line, Origin, Section

# Artifacts: CLEANUP, not evidence of who wrote the text. Source for the patterns: chatbot residue and invisible
# characters catalogued in Wikipedia's "Signs of AI writing" (Unicode: U+200B/200C/200D zero-width space/non-joiner/
# joiner, U+2060 word joiner, U+FEFF byte-order mark).
ARTIFACTS = (
    r"[​‌‍⁠﻿]",
    r"\s*as an ai language model\b[,.]?",
    r"certainly!\s*here['’]s\s*:?\s*",
    r"\*\*",
)

# Weak signal, swap list. Source: excess-vocabulary words in Kobak et al. 2025, "Delving into LLM-assisted writing in
# biomedical publications through excess vocabulary" (arXiv 2406.07016: delves, showcasing, underscores) and
# Wikipedia "Signs of AI writing" (tapestry, "in the realm of"). A weak signal, so the report says so. LLM text gets
# every swap; user text only the ones not in FLAG_ONLY_IN_USER_TEXT.
SAFE_SWAPS = {
    "delve into": "explore", "delves into": "explores", "delved into": "explored", "delving into": "exploring",
    "showcasing": "showing",
    "underscores": "highlights",
    "tapestry": "mix",
    "in the realm of": "in",
}
FLAG_ONLY_IN_USER_TEXT = ("showcasing", "underscores", "tapestry")

# Weak signal, ambiguous words: also ordinary English, so they are only flagged, in user and LLM text alike. Source:
# Liang et al. 2024, "Mapping the Increasing Use of Large Language Models in Scientific Papers" (arXiv 2404.01268:
# intricate, potential) and Kobak et al. 2025 (arXiv 2406.07016: findings).
AMBIGUOUS = ("intricate", "potential", "findings")

# Weak signal: the em dash. Source: Wikipedia "Signs of AI writing". Flagged in user text, replaced in LLM text.
EM_DASH = "—"

Kind = Literal["strip", "swap", "flag"]


@dataclass(frozen=True)
class Change:
    kind: Kind
    found: str
    replacement: str = ""
    source_fact_id: str | None = None

    @property
    def weak(self) -> bool:
        """Everything but a strip is a weak signal, not proof of who wrote the text."""
        return self.kind != "strip"


def _phrase(text: str) -> str:
    return r"\s+".join(map(re.escape, text.split()))


_ARTIFACT = re.compile("|".join(ARTIFACTS), re.I)


def _words(words) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(_phrase(k) for k in sorted(words, key=len, reverse=True)) + r")\b", re.I)


_SWAP = _words(SAFE_SWAPS)
_USER_SWAP = _words(k for k in SAFE_SWAPS if k not in FLAG_ONLY_IN_USER_TEXT)
_FLAG_LLM = _words(AMBIGUOUS)
_FLAG_USER = _words((*AMBIGUOUS, *FLAG_ONLY_IN_USER_TEXT))
_DASH = re.compile(rf"\s*{EM_DASH}\s*")


def _swap(match: re.Match[str]) -> str:
    new = SAFE_SWAPS[" ".join(match[0].lower().split())]
    return new.capitalize() if match[0][0].isupper() else new


def _apply(pattern: re.Pattern[str], text: str, make: Kind, changes: list[Change], to=None) -> str:
    def sub(m: re.Match[str]) -> str:
        new = to(m) if to else ""
        changes.append(Change(make, m[0].strip(), new))
        return new

    return pattern.sub(sub, text)


def clean(text: str, origin: Origin) -> tuple[str, list[Change]]:
    """The cleaned text and every change or flag. User text means anything that is not a suggestion."""
    llm = origin is Origin.SUGGESTION
    changes: list[Change] = []
    while True:  # one removal can expose another ("**" split by a zero-width space), so repeat until stable
        before = text
        text = _apply(_ARTIFACT, text, "strip", changes)
        text = _apply(_SWAP if llm else _USER_SWAP, text, "swap", changes, _swap)
        if llm:
            text = _apply(_DASH, text, "swap", changes, lambda m: ", ")
        if text == before:
            break
    changes += [Change("flag", m[0]) for m in (_FLAG_LLM if llm else _FLAG_USER).finditer(text)]
    if not llm:
        changes += [Change("flag", EM_DASH) for _ in re.finditer(EM_DASH, text)]
    return text, changes


def clean_document(doc: Document) -> tuple[Document, list[Change]]:
    """Clean every line by its own origin. Lines left empty are dropped."""
    changes: list[Change] = []

    def line(item: Line) -> Line:
        text, found = clean(item.text, item.origin)
        changes.extend(replace(c, source_fact_id=item.source_fact_id) for c in found)
        return replace(item, text=text)

    def entry(item: Entry) -> Entry:
        paragraph = line(item.paragraph) if item.paragraph else None
        return Entry(
            line(item.heading) if item.heading else None,
            paragraph if paragraph and paragraph.text.strip() else None,
            tuple(b for b in map(line, item.bullets) if b.text.strip()),
        )

    return (
        replace(
            doc,
            name=line(doc.name),
            intro=tuple(map(line, doc.intro)),
            sections=tuple(Section(s.title, tuple(map(entry, s.entries))) for s in doc.sections),
        ),
        changes,
    )
