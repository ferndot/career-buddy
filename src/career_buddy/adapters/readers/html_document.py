"""Reads a saved document's stored HTML back into a Document, so the renderers and the ATS check see what the user has.

Only the allowed tags count (h1 h2 h3 p ul li; strong, em and br stay inside a line). Anything else is ignored; script and
style content is dropped. A slot's text is `texts[slot id]` (see domain/slots.py for how that is found) in place of the
element's own text; the slots named in `own` count as the user's own words.
"""

from __future__ import annotations

from html.parser import HTMLParser

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.slots import Slot

_LINE_TAGS = {"h1", "h2", "h3", "p", "li"}
_DROPPED = {"script", "style"}


class _Reader(HTMLParser):
    def __init__(self, texts: dict[str, str], own: frozenset[str]) -> None:
        super().__init__()
        self._texts = texts
        self._own = own
        self.slots: list[Slot] = []
        self.name: Line | None = None
        self.intro: list[Line] = []
        self.sections: list[tuple[str, list[dict]]] = []  # (title, entries); an entry is {heading, paragraph, bullets}
        self._entry: dict | None = None
        self._open: tuple[str, dict[str, str], list[str]] | None = None  # the line being read: tag, attributes, text
        self._dropped = 0
        self._list_entry: dict | None = None  # where the bullets of the current <ul> go

    def _section(self) -> list[dict]:
        if not self.sections:
            self.sections.append(("", []))
        return self.sections[-1][1]

    def _new_entry(self) -> dict:
        self._entry = {"heading": None, "paragraph": None, "bullets": []}
        self._section().append(self._entry)
        return self._entry

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROPPED:
            self._dropped += 1
        elif tag == "br" and self._open:
            self._open[2].append(" ")
        elif tag == "ul":
            entry = self._entry
            self._list_entry = entry if entry and not entry["bullets"] else self._new_entry()
        elif tag in _LINE_TAGS and not self._open and not self._dropped:
            self._open = (tag, {k: v or "" for k, v in attrs}, [])

    def handle_data(self, data: str) -> None:
        if self._open and not self._dropped:
            self._open[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROPPED:
            self._dropped = max(0, self._dropped - 1)
        elif self._open and self._open[0] == tag:
            self._finish(*self._open)
            self._open = None
        elif tag == "ul":
            self._list_entry = None

    def _finish(self, tag: str, attrs: dict[str, str], parts: list[str]) -> None:
        slot = attrs.get("data-slot", "")
        own_text = " ".join("".join(parts).split())
        if slot:
            self.slots.append(Slot(slot, tuple(attrs.get("data-fact-id", "").split()), attrs.get("data-field", ""), own_text))
        raw = self._texts[slot] if slot in self._texts else own_text
        # A person's text may hold several lines (a freeform edit adds them): each is a line of this tag. An empty text is a removed line.
        for text in ([" ".join(line.split()) for line in raw.splitlines()] if tag in {"p", "li"} else [" ".join(raw.split())]):
            if text:
                self._add(tag, attrs, slot, text)

    def _add(self, tag: str, attrs: dict[str, str], slot: str, text: str) -> None:
        if tag == "h2":
            self.sections.append((text, []))
            self._entry = None
            return
        origin = Origin.USER if slot in self._own else _origin(attrs.get("data-origin", ""))
        line = Line(text, (attrs.get("data-fact-id") or "").split(" ")[0] or None, origin)
        entry = self._entry
        if tag == "h1" and self.name is None:
            self.name = line
        elif tag == "p" and "intro" in attrs.get("class", "").split() and not self.sections:
            self.intro.append(line)
        elif tag == "h3":
            self._new_entry()["heading"] = line
        elif tag == "li":
            (self._list_entry if self._list_entry is not None else self._new_entry())["bullets"].append(line)
        elif entry and entry["heading"] and not entry["paragraph"] and not entry["bullets"]:
            entry["paragraph"] = line
        else:
            self._new_entry()["paragraph"] = line


def _origin(value: str) -> Origin:
    try:
        return Origin(value)
    except ValueError:
        return Origin.USER  # typed into the editor: no origin recorded


def _read(html: str, texts: dict[str, str], own: frozenset[str]) -> _Reader:
    reader = _Reader(texts, own)
    reader.feed(html)
    reader.close()
    return reader


def read_slots(html: str) -> list[Slot]:
    """The slots of a layout, in reading order, with the placeholder text each holds."""
    return _read(html, {}, frozenset()).slots


def read_document(html: str, texts: dict[str, str] | None = None, own: frozenset[str] = frozenset(), label: str = "Resume") -> Document:
    reader = _read(html, texts or {}, own)
    sections = tuple(
        Section(title, tuple(Entry(e["heading"], e["paragraph"], tuple(e["bullets"])) for e in entries))
        for title, entries in reader.sections
    )
    return Document(reader.name or Line(""), tuple(reader.intro), sections, label)
