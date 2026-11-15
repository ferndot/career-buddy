"""Splits free text into achievement bullets and prose."""

from __future__ import annotations

BULLETS = ("-", "*", "•", "–", "●", "▪", "■", "◦")


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
