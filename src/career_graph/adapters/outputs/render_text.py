"""Renders a Document as plain text."""

from __future__ import annotations

from career_graph.domain.document import Document, Style


class TextRenderer:
    format = "txt"
    extension = "txt"
    media_type = "text/plain"

    def render(self, doc: Document, style: Style) -> bytes:
        out = [doc.name.text, *(line.text for line in doc.intro)]
        for section in doc.sections:
            out += ["", section.title] if section.title else [""]
            for entry in section.entries:
                out += [line.text for line in filter(None, (entry.heading, entry.paragraph))]
                out += [f"- {b.text}" for b in entry.bullets]
        return ("\n".join(out) + "\n").encode()
