"""Splits free text into achievement bullets and prose."""

from __future__ import annotations

# U+FFFD is what pdfminer gives for a bullet glyph it cannot map.
BULLETS = ("-", "*", "•", "–", "●", "▪", "■", "◦", "�")


def split_bullets(text: str) -> tuple[tuple[str, ...], str]:
    bullets: list[str] = []
    prose: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(BULLETS):
            bullets.append(stripped.lstrip("".join(BULLETS)).strip())
        elif stripped:
            prose.append(stripped)
    return tuple(b for b in bullets if b), " ".join(prose)


SKILL_SEPARATORS = frozenset(",;|*•·•�")


def split_skills(line: str) -> list[str]:
    """One line of a skills section as separate skills. Separators inside brackets stay put: "Python (3.11, pandas)"."""
    items: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in line:
        depth = depth + 1 if ch in "([" else max(0, depth - 1) if ch in ")]" else depth
        if ch in SKILL_SEPARATORS and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    items.append("".join(current))
    cleaned = [s.strip().lstrip("".join(BULLETS)).strip().rstrip(".").strip() for s in items]
    return list(dict.fromkeys(s for s in cleaned if s))  # first wording wins; exact repeats go
