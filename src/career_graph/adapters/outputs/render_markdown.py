"""Renders a Document as Markdown."""

from __future__ import annotations

from career_graph.domain.document import Document, Style


class MarkdownRenderer:
    format = "markdown"
    extension = "md"
    media_type = "text/markdown"

    def render(self, doc: Document, style: Style) -> bytes:
        out = [f"# {doc.name.text}", ""]
        for line in doc.intro:
            out += [line.text, ""]
        for section in doc.sections:
            if section.title:
                out.append(f"## {section.title}")
            for entry in section.entries:
                if entry.heading:
                    out.append(f"### {entry.heading.text}")
                if entry.paragraph:
                    out.append(entry.paragraph.text)
                out += [f"- {b.text}" for b in entry.bullets]
                out.append("")
        return "\n".join(out).encode()
