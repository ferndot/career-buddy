"""Rule-based extraction from resume-style text. Works offline; no model required."""

from __future__ import annotations

import re

from career_graph.domain.builder import BatchBuilder
from career_graph.domain.model import FactBatch
from career_graph.domain.text import BULLETS, split_bullets

_HEADING = re.compile(
    r"^(?:#+\s*)?(?:(?:professional|technical|core)\s+)?(experience|work|employment|skills|education|summary|profile|about)\b",
    re.I,
)
_POSITION = re.compile(r"^(?P<title>.+?)\s+(?:at|@|—|\|)\s+(?P<org>[^,|()]+)")
_DATES = r"(?:[A-Za-z]{3,9}\s+)?\d{4}\s*(?:-|–|—|to)\s*(?:(?:[A-Za-z]{3,9}\s+)?\d{4}|present)"
_DATES_IN = re.compile(_DATES, re.I)
_DATES_ONLY = re.compile(_DATES + "$", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_EXPERIENCE = ("experience", "work", "employment")


def _contact(line: str) -> dict[str, str]:
    """Email and phone found on a line. A phone needs 9+ digits so a year range is not one."""
    found = {}
    if email := _EMAIL.search(line):
        found["email"] = email.group()
    phone = next((m.group() for m in _PHONE.finditer(line) if sum(c.isdigit() for c in m.group()) >= 9), None)
    if phone:
        found["phone"] = phone
    return found


def _stacked(lines: list[str]) -> list[str] | None:
    """[organization, title, dates] when three lines in a row are laid out that way, else None."""
    if len(lines) < 3 or not _DATES_ONLY.match(lines[2]):
        return None
    if any(line.startswith(BULLETS) or _DATES_ONLY.match(line) for line in lines[:2]):
        return None
    return lines[:3]


class HeuristicExtractor:
    async def extract(self, text: str, source: str) -> FactBatch:
        b = BatchBuilder(source)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        name, contact, section = "", {}, ""
        # Each entry: [title, organization, period, achievements]
        positions: list[list] = []
        skills: list[str] = []
        schools: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            heading = _HEADING.match(line.lstrip("#").strip())
            if heading and len(line) < 40:
                section = heading.group(1).lower()
            elif not section:
                if found := _contact(line):
                    contact = {**found, **contact}
                elif not name:
                    name = line
            elif section in _EXPERIENCE:
                if stacked := _stacked(lines[i - 1 : i + 2]):
                    positions.append([stacked[1], stacked[0], stacked[2], []])
                    i += 2
                elif (match := _POSITION.match(line)) and not line.startswith(BULLETS):
                    dates = _DATES_IN.search(line)
                    positions.append([match["title"].strip(), match["org"].strip(), dates.group(0) if dates else "", []])
                elif positions:
                    bullets, prose = split_bullets(line)
                    positions[-1][3].extend(bullets or ((prose,) if prose else ()))
            elif section == "skills":
                skills += [s.strip().lstrip("".join(BULLETS)).strip() for s in re.split(r"[,;]", line)]
            elif section == "education":
                schools.append(line)

        person = b.person(name or "Me", **contact)
        for skill in filter(None, skills):
            b.skill(person, skill)
        for school in schools:
            b.education(person, school)
        for title, org, period, achievements in positions:
            b.position(person, title, org, achievements=tuple(achievements), period=period)
        return b.build()
