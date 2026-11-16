"""When a position or education was held, at year precision. Pure: parses the text the user or a source wrote."""

from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR = re.compile(r"\d{4}")
_OPEN = re.compile(r"[-–—]|present|current", re.I)  # a lone year followed by a dash has no end yet
_DASH_FIRST = re.compile(r"\s*[-–—]")


@dataclass(frozen=True)
class Period:
    """First and last year. An unknown start is -inf, a still-running stint is inf."""

    start: float
    end: float

    def overlaps(self, other: Period) -> bool:
        return self.start <= other.end and other.start <= self.end


def period_of(attrs: dict[str, str]) -> Period | None:
    """Read `period`, or `started`/`finished` when the period text is missing. None when no year is given."""
    text = attrs.get("period") or f"{attrs.get('started', '')} - {attrs.get('finished', '')}"
    years = [int(y) for y in _YEAR.findall(text)]
    if not years:
        return None
    if len(years) > 1:
        return Period(min(years[0], years[1]), max(years[0], years[1]))  # "2021 - 2019" is read as written by a person, not as a time machine
    if _DASH_FIRST.match(text):  # only an end year: the start is unknown, the stint is over
        return Period(float("-inf"), years[0])
    return Period(years[0], float("inf") if _OPEN.search(text) else years[0])
