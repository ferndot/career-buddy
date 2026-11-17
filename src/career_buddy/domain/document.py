"""The Document model: one pure, single-column structure that every renderer draws (plan D2)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Origin(StrEnum):
    FACT = "fact"
    USER = "user"
    SUGGESTION = "suggestion"
    BOILERPLATE = "boilerplate"


@dataclass(frozen=True)
class Layout:
    """How a template arranges its page. Data: the stored html wraps its parts in these classes and `css` styles them
    (adapters/outputs/render_html.py); the wizard draws the same arrangement from it.

    `side` are the headings of trailing sections that sit in a side column beside the rest."""

    header: Literal["plain", "centered", "band"] = "plain"
    side: tuple[str, ...] = ()
    css: str = ""


@dataclass(frozen=True)
class Line:
    text: str
    source_fact_id: str | None = None
    origin: Origin = Origin.FACT
    # Layout hints for a saved document, not part of what a line says, so they do not take part in comparisons.
    field: str = dataclasses.field(default="", compare=False)  # which value of the source fact this line shows; "" is fixed wording (domain/slots.py)
    cites: tuple[str, ...] = dataclasses.field(default=(), compare=False)  # fact ids behind a line several facts make up, such as the skills list
    slot: str = dataclasses.field(default="", compare=False)  # the slot id a written line already has (domain/written.py); "" lets the layout number it


@dataclass(frozen=True)
class Entry:
    """One block in a section: an optional heading line, an optional paragraph, then bullets."""

    heading: Line | None = None
    paragraph: Line | None = None
    bullets: tuple[Line, ...] = ()

    def lines(self) -> list[Line]:
        return [*filter(None, (self.heading, self.paragraph)), *self.bullets]


@dataclass(frozen=True)
class Section:
    title: str
    entries: tuple[Entry, ...] = ()


@dataclass(frozen=True)
class Document:
    name: Line
    intro: tuple[Line, ...] = ()  # contact line first, then headline
    sections: tuple[Section, ...] = ()
    label: str = "Resume"  # what the document is: names the download and the DOCX/HTML title
    layout: Layout = dataclasses.field(default=Layout(), compare=False)  # the template's page arrangement: html and pdf draw it, docx keeps the header

    def lines(self) -> list[str]:
        """Every visible line in reading order. This is what the ATS check expects back."""
        out = [self.name.text, *(line.text for line in self.intro)]
        for section in self.sections:
            out += [section.title] if section.title else []  # letters have one untitled section
            out += [line.text for entry in section.entries for line in entry.lines()]
        return out

    def headings(self) -> list[str]:
        return [section.title for section in self.sections if section.title]


@dataclass(frozen=True)
class Style:
    font: Literal["sans", "serif"] = "sans"
    paper: Literal["letter", "a4"] = "letter"
