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
_DATES = r"(?:[A-Za-z]{3,9}\s+)?\d{4}\s*(?:-|–|—|to|�)\s*(?:(?:[A-Za-z]{3,9}\s+)?\d{4}|present)"
_DATES_IN = re.compile(_DATES, re.I)
_DATES_ONLY = re.compile(_DATES + "$", re.I)
_COMPANY = re.compile(r"^(?P<org>.+?)\s+(?P<dates>" + _DATES + ")$", re.I)  # "Company  Mon YYYY – Present"
_TITLE = re.compile(r"^[A-Z0-9][^.,;:]{0,59}$")  # short, capitalised, no sentence punctuation: not a wrapped bullet
_LABELS = {"languages", "frameworks & libraries", "cloud, data & tools", "concepts", "ai & machine learning"}
_ITEM_SEPARATORS = re.compile(r"[,;�]")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")  # pdfminer sometimes drops the opening parenthesis
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


def _period(dates: str) -> str:
    return dates.replace("�", "–")


def _is_label(line: str) -> bool:
    return line.endswith(":") or line.lower() in _LABELS


class HeuristicExtractor:
    async def extract(self, text: str, source: str) -> FactBatch:
        b = BatchBuilder(source)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        name, contact, section = "", {}, ""
        # Each entry: [title, organization, period, achievements]
        positions: list[list] = []
        group: tuple[str, str] | None = None  # (organization, period) while a company line's titles follow
        skills: list[str] = []
        # Each entry: (school, degree, period). Lines gather in `pending` until a date range closes the entry.
        schools: list[tuple[str, str, str]] = []
        pending: list[str] = []

        def flush_pending() -> None:
            schools.extend((line, "", "") for line in pending)  # no date range: every line is a school
            pending.clear()

        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            heading = _HEADING.match(line.lstrip("#").strip())
            if heading and len(line) < 40:
                flush_pending()
                section, group = heading.group(1).lower(), None
            elif not section:
                if found := _contact(line):
                    contact = {**found, **contact}
                elif not name:
                    name = line
            elif section in _EXPERIENCE:
                if stacked := _stacked(lines[i - 1 : i + 2]):
                    positions.append([stacked[1], stacked[0], _period(stacked[2]), []])
                    i += 2
                    group = None
                elif line.startswith(BULLETS):
                    if positions:
                        positions[-1][3].extend(split_bullets(line)[0])
                elif (company := _COMPANY.match(line)) and not _POSITION.match(line):
                    group = (company["org"].strip(), _period(company["dates"]))
                elif group and _TITLE.match(line):
                    positions.append([line, *group, []])
                elif match := _POSITION.match(line):
                    dates = _DATES_IN.search(line)
                    positions.append([match["title"].strip(), match["org"].strip(), _period(dates.group(0)) if dates else "", []])
                    group = None
                elif positions:
                    bullets, prose = split_bullets(line)
                    positions[-1][3].extend(bullets or ((prose,) if prose else ()))
            elif section == "skills":
                if not _is_label(line):
                    skills += [s.strip().lstrip("".join(BULLETS)).strip() for s in _ITEM_SEPARATORS.split(line)]
            elif section == "education":
                if _DATES_ONLY.match(line) and pending:
                    schools.append((pending[0], ", ".join(pending[1:]), _period(line)))
                    pending.clear()
                else:
                    pending.append(line)
        flush_pending()

        person = b.person(name or "Me", **contact)
        for skill in filter(None, skills):
            b.skill(person, skill)
        for school, degree, period in schools:
            b.education(person, school, degree, period=period)
        for title, org, period, achievements in positions:
            b.position(person, title, org, achievements=tuple(achievements), period=period)
        return b.build()
