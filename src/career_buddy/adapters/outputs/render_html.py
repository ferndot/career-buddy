"""Renders a Document as single-column HTML. The PDF renderer prints this same page."""

from __future__ import annotations

from html import escape
from itertools import count

from career_buddy.domain.document import Document, Line, Style

_FONTS = {"sans": "Helvetica, Arial, sans-serif", "serif": "'Times New Roman', Times, serif"}


def document_css(style: Style, extra_css: str = "") -> str:
    return (
        f"body{{font-family:{_FONTS[style.font]};font-size:11pt;line-height:1.35;max-width:760px;margin:2rem auto;"
        "padding:0 1rem;font-variant-ligatures:none}"
        "h1{font-size:20pt;margin:0}h2{font-size:13pt;margin:1rem 0 .3rem}h3{font-size:11pt;margin:.6rem 0 .2rem}"
        "p{margin:.2rem 0}ul{margin:.2rem 0;padding-left:1.2rem}" + extra_css
    )


def stored_html(doc: Document) -> str:
    """The editable body kept with a saved document: allowed tags only, each text line a slot bound to its fact.

    Section titles are fixed headings, not slots. The `intro` class marks the lines under the name, so a letter's
    untitled section reads back apart from them.
    """
    slots = count(1)

    def line(tag: str, text: Line, field: str = "text", css: str = "") -> str:
        fact = f' data-fact-id="{escape(text.source_fact_id)}"' if text.source_fact_id else ""
        cls = f' class="{css}"' if css else ""
        return (f'<{tag}{cls} data-slot="s{next(slots)}"{fact} data-field="{field}" data-origin="{text.origin.value}">'
                f"{escape(text.text)}</{tag}>")

    parts = [line("h1", doc.name), *(line("p", intro, css="intro") for intro in doc.intro)]
    for section in doc.sections:
        if section.title:
            parts.append(f'<h2 data-origin="boilerplate">{escape(section.title)}</h2>')
        for entry in section.entries:
            if entry.heading:
                parts.append(line("h3", entry.heading, "title"))
            if entry.paragraph:
                parts.append(line("p", entry.paragraph))
            if entry.bullets:
                parts.append("<ul>" + "".join(line("li", b) for b in entry.bullets) + "</ul>")
    return "\n".join(parts)


def html_page(doc: Document, style: Style, extra_css: str = "") -> str:
    e = escape
    parts = [f"<h1>{e(doc.name.text)}</h1>", *(f"<p>{e(line.text)}</p>" for line in doc.intro)]
    for section in doc.sections:
        if section.title:
            parts.append(f"<h2>{e(section.title)}</h2>")
        for entry in section.entries:
            if entry.heading:
                parts.append(f"<h3>{e(entry.heading.text)}</h3>")
            if entry.paragraph:
                parts.append(f"<p>{e(entry.paragraph.text)}</p>")
            if entry.bullets:
                parts.append("<ul>" + "".join(f"<li>{e(b.text)}</li>" for b in entry.bullets) + "</ul>")
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(doc.name.text)} - {e(doc.label)}</title>"
        f"<style>{document_css(style, extra_css)}</style></head><body>{''.join(parts)}</body></html>"
    )


class HtmlRenderer:
    format = "html"
    extension = "html"
    media_type = "text/html"

    def render(self, doc: Document, style: Style) -> bytes:
        return html_page(doc, style).encode()
