"""What is known about an achievement, separate from the wording any one source used. Pure."""

from __future__ import annotations

from collections.abc import Sequence

from career_buddy.domain.model import Fact

KNOWLEDGE_KEYS = ("result", "tools", "project")  # the achievement attributes the extractor fills


def details(fact: Fact) -> str:
    """Title and details of one fact, without its position or employer. Used for duplicate scoring."""
    return " ".join(p for p in [fact.title, *(fact.attributes.get(k, "") for k in KNOWLEDGE_KEYS)] if p)


def knowledge(fact: Fact, absorbed: Sequence[Fact] = ()) -> str:
    """The facts behind an achievement, merged from every source that stated it. This is what wording is generated from.

    A fact imported before details were extracted has only its title, so the result is then just the title."""
    group = (fact, *absorbed)
    titles = _unique([fact.title, *(f.title for f in absorbed)])
    lines = titles[:1]
    if others := titles[1:]:
        lines.append("Other wordings: " + " / ".join(others))
    for key in KNOWLEDGE_KEYS:
        if values := _unique(f.attributes.get(key, "") for f in group):
            lines.append(f"{key.capitalize()}: " + " / ".join(values))
    return "\n".join(lines)


def _unique(values) -> list[str]:
    """Non-empty values, first occurrence wins, compared ignoring case and spacing."""
    seen: dict[str, str] = {}
    for value in values:
        text = " ".join(value.split())
        if text and text.lower() not in seen:
            seen[text.lower()] = text
    return list(seen.values())
