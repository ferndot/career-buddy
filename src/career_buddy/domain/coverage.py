"""What the checks made of a written document, and when the writer stops revising. Pure.

Besides the claims that failed the facts, a resume can fall short in two ways the writer cannot see: a relevant role is missing or thin,
and the rendered pages are over (or well under) the length. `issues` finds them; each carries the text the writer is told and the ids of
the achievements it has not used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from career_buddy.domain.generation import Brief, Claim, Rejection
from career_buddy.domain.written import WrittenDocument

MAX_REVISIONS = 1  # after the first answer the writer gets one more try: at most two model calls
RECENT_YEARS = 15  # a role that ended within this many years is relevant, whatever the posting says
MIN_FILL = 0.75  # a one-page resume that fills less of its page has room for more
THIN = 1  # a relevant role with this many bullets or fewer, and achievements unused, is thin


@dataclass(frozen=True)
class Pages:
    """A document as printed: its page count, how much of the last page's printable height holds text (0 to 1) and the text lines on page one."""

    count: int
    last_fill: float
    lines_per_page: int


@dataclass(frozen=True)
class Issue:
    """Something to fix that is not a rejected claim. `fact_ids` are the achievements that could fill it."""

    code: Literal["missing_position", "thin_position", "too_long", "room_left", "weak_fit"]
    text: str
    fact_ids: tuple[str, ...] = ()
    slots: tuple[str, ...] = ()  # texts the writer may rewrite to fix it (domain/fit.py)


@dataclass(frozen=True)
class Checked:
    """A validated document with the claims that passed the facts (by slot id), those that did not, and, for a resume, how it printed and what to fix."""

    doc: WrittenDocument
    kept: dict[str, Claim]
    rejected: list[Rejection]
    pages: Pages | None = None  # None when it was not measured (a letter, or no browser)
    issues: tuple[Issue, ...] = ()


def next_step(rounds: int, checked: Checked, failed: bool) -> str:
    """`revise` while something is rejected or short and a revision is left; `end` otherwise, and always after a failed call."""
    return "revise" if (checked.rejected or checked.issues) and rounds < MAX_REVISIONS and not failed else "end"


def _year(text: str) -> int | None:
    found = re.search(r"\b(?:19|20)\d{2}\b", text)
    return int(found[0]) if found else None


def relevant_positions(brief: Brief, year: int) -> list[str]:
    """Positions with achievements that match a job term (the position's title or any achievement) or ended within RECENT_YEARS of `year`.
    A missing, open or unreadable end counts as recent."""
    terms = [re.compile(rf"(?<!\w){re.escape(t.lower())}(?!\w)") for t in brief.terms if t.strip()]
    out = []
    for p in (f for f in brief.facts if f.kind == "position"):
        words = [a.text for a in brief.facts if a.kind == "achievement" and a.position_id == p.id]
        end = _year(p.finished)
        if words and (end is None or end >= year - RECENT_YEARS or any(t.search(" ".join([p.text, *words]).lower()) for t in terms)):
            out.append(p.id)
    return out


def length_text(pages: Pages, limit: int, spare: bool) -> str | None:
    """What to tell the writer about the length: how many lines over, or, for a one-page resume that fills under MIN_FILL while achievements
    are unused (`spare`), how many lines of room. None when it is fine."""
    lines = max(pages.lines_per_page, 1)
    if pages.count > limit:
        over = max(1, round((pages.count - limit - 1 + pages.last_fill) * lines))
        return (f"The resume prints on {pages.count} pages and the limit is {limit}: it is about {over} lines over. "
                "Remove or shorten the least relevant bullets; keep every relevant role.")
    if limit == 1 and pages.last_fill < MIN_FILL and spare:
        return f"The resume fills {round(pages.last_fill * 100)}% of its page: there is room for about {max(1, round((1 - pages.last_fill) * lines))} lines. Add bullets for the most relevant unused achievements."
    return None


def issues(brief: Brief, doc: WrittenDocument, pages: Pages | None, year: int) -> tuple[Issue, ...]:
    """For a resume: each relevant role missing from the document, each relevant role left thin (not while it is over length), and the length."""
    if brief.kind != "resume":
        return ()
    held: dict[str, int] = {}  # position -> the bullets of the item that holds it
    cited: set[str] = set()
    for s in doc.sections:
        for it in s.items:
            cited |= {*it.fact_ids, *(i for b in it.bullets for i in b.fact_ids)}
            if s.key == "experience":
                held |= {p: len(it.bullets) for p in (it.position_id, *it.also)}
    unused = lambda pid: tuple(f.id for f in brief.facts if f.kind == "achievement" and f.position_id == pid and f.id not in cited)  # noqa: E731
    title = {f.id: f.text for f in brief.facts if f.kind == "position"}
    long = pages is not None and pages.count > brief.caps.pages
    relevant = relevant_positions(brief, year)
    found = [Issue("missing_position", f'"{title[p]}" ({p}) is relevant for this role and missing. Add it with bullets from its achievements.', unused(p))
             for p in relevant if p not in held]
    found += [Issue("thin_position", f'"{title[p]}" ({p}) is relevant but has only {held[p]} bullet(s) while achievements are unused.', unused(p))
              for p in relevant if p in held and held[p] <= THIN and unused(p) and not long]
    if pages and (text := length_text(pages, brief.caps.pages, any(unused(p) for p in relevant))):
        found.append(Issue("too_long" if long else "room_left", text, tuple(i for p in relevant for i in unused(p)) if not long else ()))
    return tuple(found)
