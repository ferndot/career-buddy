"""Reads a saved document's stored HTML back into a Document, so the renderers and the ATS check see what the user has.

Only the allowed tags count (h1 h2 h3 p ul li; strong, em and br stay inside a line). Anything else is ignored; script and
style content is dropped. Text slots resolve through `overrides` (slot id -> the user's wording) before the stored text.
"""

from __future__ import annotations

from html.parser import HTMLParser

from career_buddy.domain.document import Document, Entry, Line, Origin, Section

_LINE_TAGS = {"h1", "h2", "h3", "p", "li"}
_DROPPED = {"script", "style"}


class _Reader(HTMLParser):
    def __init__(self, overrides: dict[str, str]) -> None:
        super().__init__()
        self._overrides = overrides
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
        text = " ".join((self._overrides[slot] if slot in self._overrides else "".join(parts)).split())
        if not text:
            return
        if tag == "h2":
            self.sections.append((text, []))
            self._entry = None
            return
        origin = Origin.USER if slot in self._overrides else _origin(attrs.get("data-origin", ""))
        line = Line(text, attrs.get("data-fact-id") or None, origin)
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


def read_document(html: str, overrides: dict[str, str] | None = None, label: str = "Resume") -> Document:
    reader = _Reader(overrides or {})
    reader.feed(html)
    reader.close()
    sections = tuple(
        Section(title, tuple(Entry(e["heading"], e["paragraph"], tuple(e["bullets"])) for e in entries))
        for title, entries in reader.sections
    )
    return Document(reader.name or Line(""), tuple(reader.intro), sections, label)
