"""How closely written text must follow the facts. Pure.

Specifics are never loosened: numbers, titles, employers, dates, degrees, schools and any tool, skill or certification the facts do not
name are checked the same at every level (domain/rewording.py `specifics`, domain/grounding.py `verify_prose`). The level changes
wording only, here how much longer than the facts it cites a text may run, so a paraphrase, a stronger verb or two achievements merged
into one bullet can pass. Generic wording a model infers (lowercase, such as "container orchestration" for Kubernetes) is never
checked at any level: only names, numbers and tool-shaped words are.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

Strictness = Literal["strict", "balanced", "loose"]
LEVELS: tuple[Strictness, ...] = ("strict", "balanced", "loose")
DEFAULT: Strictness = "balanced"


class Growth(NamedTuple):
    bullet: float  # a bullet or education line may be this many times the cited text
    prose: int  # a summary, skills line or paragraph: this many times, plus `allowance` characters
    allowance: int


GROWTH: dict[str, Growth] = {"strict": Growth(1.3, 6, 300), "balanced": Growth(1.8, 8, 400), "loose": Growth(2.5, 10, 500)}
