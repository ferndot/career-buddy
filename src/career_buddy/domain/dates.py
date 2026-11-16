"""Partial dates for positions and education: "2021", "2021-03" or "2021-03-14". The precision is the length.

A fact keeps them in its `started` and `finished` attributes. `finished` may also be "present". Pure: no clock, no storage.
"""

from __future__ import annotations

import re
from datetime import date

from career_buddy.domain.model import InvalidFact

PRESENT = "present"
BOUNDS = ("started", "finished")
_ISO = re.compile(r"([0-9]{4})(?:-([0-9]{2})(?:-([0-9]{2}))?)?")
_MONTHS = "january february march april may june july august september october november december".split()
_OPEN_WORDS = {PRESENT, "current", "now", "ongoing"}
_LEGACY_BOUND = re.compile(r"(?:([A-Za-z]{3,9})\.?\s+)?([0-9]{4})")
_LEGACY_SPLIT = re.compile(r"\s*(?:[–—-]|\bto\b)\s*", re.I)


def parse(text: str) -> tuple[int, ...] | None:
    """(year,), (year, month) or (year, month, day). None unless the text is exactly a real partial ISO date."""
    match = _ISO.fullmatch(text)
    if not match:
        return None
    parts = tuple(int(g) for g in match.groups() if g is not None)
    try:
        date(*parts, *(1,) * (3 - len(parts)))  # rejects year 0, month 13 and 30 February
    except ValueError:
        return None
    return parts


def format_date(text: str) -> str:
    """"2019", "Mar 2019" or "14 Mar 2019"; "present" as "Present". Text that is no date comes back as written."""
    if text.lower() == PRESENT:
        return "Present"
    parts = parse(text)
    if not parts:
        return text
    year, *rest = parts
    return " ".join([*(str(d) for d in rest[1:]), *(_MONTHS[m - 1][:3].title() for m in rest[:1]), f"{year:04d}"])


def format_range(start: str, end: str) -> str:
    """"2019 – 2021", "Mar 2019 – Present", "2019" (one year), or just the one bound given. An open end is Present."""
    if start and not end:
        end = PRESENT
    s, e = format_date(start), format_date(end)
    return f"{s} – {e}" if s and e and s != e else s or e


def _ordered(start: str, end: str) -> bool:
    """False only when both bounds are dates and the end is before the start, compared at the coarser precision."""
    a, b = parse(start), parse(end)
    if not a or not b:
        return True
    n = min(len(a), len(b))
    return a[:n] <= b[:n]


def _legacy_bound(text: str) -> str | None:
    """"Mar 2019" or "2019" as partial ISO; None when it is not clearly one."""
    match = _LEGACY_BOUND.fullmatch(text)
    if not match:
        return None
    name, year = match.groups()
    month = next((i for i, full in enumerate(_MONTHS, 1) if full.startswith(name.lower())), None) if name else 0
    iso = year if month == 0 else f"{year}-{month:02d}" if month else ""
    return iso if parse(iso) else None


def migrate_period(text: str) -> dict[str, str] | None:
    """started/finished from free text like "2019 - 2021", "Mar 2019 - Present" or "2019". None unless it reads clearly."""
    parts = [p.strip() for p in _LEGACY_SPLIT.split(text.strip())]
    if len(parts) > 2:
        return None
    start = _legacy_bound(parts[0]) if parts[0] else ""
    if len(parts) == 1:
        end = start
    elif not parts[1] or parts[1].lower() in _OPEN_WORDS:
        end = PRESENT
    else:
        end = _legacy_bound(parts[1])
    if start is None or end is None or not (start or end != PRESENT) or not _ordered(start, end):
        return None
    return {k: v for k, v in zip(BOUNDS, (start, end)) if v}


def _read_bound(key: str, text: str) -> str | None:
    if parse(text) or (key == "finished" and text == PRESENT):
        return text
    if key == "finished" and text.lower() in _OPEN_WORDS:
        return PRESENT
    return _legacy_bound(text)


def with_dates(attrs: dict[str, str]) -> dict[str, str]:
    """Legacy text read as dates: started/finished like "Mar 2019", or `period` like "2019 - 2021".

    Text that does not read clearly is kept as `period` text, so none is lost."""
    raw = {k: attrs[k].strip() for k in BOUNDS if attrs.get(k, "").strip()}
    if raw:
        read = {k: _read_bound(k, v) for k, v in raw.items()}
        if all(read.values()):
            return {**{k: v for k, v in attrs.items() if k not in BOUNDS}, **read}
        if "period" in attrs:
            return attrs
        return {**{k: v for k, v in attrs.items() if k not in BOUNDS}, "period": " – ".join(raw.values())}
    if moved := migrate_period(attrs.get("period", "")):
        return {**{k: v for k, v in attrs.items() if k != "period" and k not in BOUNDS}, **moved}
    return attrs


def checked(attrs: dict[str, str]) -> dict[str, str]:
    """`attrs` with started/finished validated and `period` text migrated. Empty bounds are dropped. Raises InvalidFact."""
    out = {k: v.strip() if k in BOUNDS else v for k, v in attrs.items() if k not in BOUNDS or v.strip()}
    for key in BOUNDS:
        value = out.get(key)
        if value is None:
            continue
        if key == "finished" and value.lower() == PRESENT:
            out[key] = PRESENT
        elif not parse(value):
            raise InvalidFact(f"{key} must be a year, month or day like 2021, 2021-03 or 2021-03-14" + (", or present" if key == "finished" else ""))
    if not _ordered(out.get("started", ""), out.get("finished", "")):
        raise InvalidFact("finished is before started")
    return with_dates(out)
