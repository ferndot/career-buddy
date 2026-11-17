"""Renders a Document as HTML in its template's layout. The PDF renderer prints this same page."""

from __future__ import annotations

from html import escape

from career_buddy.domain.document import Document, Layout, Line, Style
from career_buddy.domain.slots import Role, slot_for

_FONTS = {"sans": "Helvetica, Arial, sans-serif", "serif": "'Times New Roman', Times, serif"}


def document_css(style: Style, layout: Layout | None = None, extra_css: str = "") -> str:
    return (
        f"body{{font-family:{_FONTS[style.font]};font-size:11pt;line-height:1.35;max-width:760px;margin:2rem auto;"
        "padding:0 1rem;font-variant-ligatures:none}"
        "h1{font-size:20pt;margin:0}h2{font-size:13pt;margin:1rem 0 .3rem}h3{font-size:11pt;margin:.6rem 0 .2rem}"
        "p{margin:.2rem 0}ul{margin:.2rem 0;padding-left:1.2rem}" + (layout.css if layout else "") + extra_css
    )


_ATS_CSS = "h2{text-transform:none}"  # printed capitals would read back as other headings: the ATS check wants them as the template names them
NL = chr(10)


def stored_html(doc: Document, layout: Layout | None = None) -> str:
    """The editable layout kept with a saved document: allowed tags only, each text line a slot.

    A line shown from a fact is an empty element: its text is found when the document is read (domain/slots.py), so
    nothing the facts or the user say is stored here. Fixed wording (a letter's greeting) is the slot's placeholder.
    Section titles are fixed headings, not slots. The `intro` class marks the lines under the name, so a letter's
    untitled section reads back apart from them.

    With a `layout` the parts sit in wrappers the reader ignores: a `header`, and the sections in `.main` and, for the layout's
    side headings, `.side` (`.cols` around both). Slot ids follow the document's order, not the wrappers'.
    """
    taken: set[str] = set()

    def line(tag: str, role: Role, text: Line, css: str = "") -> str:
        slot = slot_for(role, text, taken)
        ids = " ".join(slot.fact_ids or ((text.source_fact_id,) if text.source_fact_id else ()))
        fact = f' data-fact-id="{escape(ids)}"' if ids else ""
        cls = f' class="{css}"' if css else ""
        return (f'<{tag}{cls} data-slot="{escape(slot.id)}"{fact} data-field="{escape(text.field)}" data-origin="{text.origin.value}">'
                f"{escape(slot.placeholder)}</{tag}>")

    head = [line("h1", "name", doc.name), *(line("p", "intro", intro, css="intro") for intro in doc.intro)]
    main: list[str] = []
    side: list[str] = []
    for section in doc.sections:
        parts = side if layout and section.title in layout.side else main
        if section.title:
            parts.append(f'<h2 data-origin="boilerplate">{escape(section.title)}</h2>')
        for entry in section.entries:
            if entry.heading:
                parts.append(line("h3", "heading", entry.heading))
            if entry.paragraph:
                parts.append(line("p", "paragraph", entry.paragraph))
            if entry.bullets:
                parts.append("<ul>" + "".join(line("li", "bullet", b) for b in entry.bullets) + "</ul>")
    if layout is None:
        return NL.join([*head, *main])
    columns = f'<div class="main">{NL.join(main)}</div>' + (f'<div class="side">{NL.join(side)}</div>' if side else "")
    return NL.join([f'<header class="{layout.header}">', *head, "</header>", f'<div class="cols">{columns}</div>'])


def html_page(doc: Document, style: Style, extra_css: str = "") -> str:
    """The page as the template lays it out: the header, then the sections in `.main` and the layout's side headings in `.side`."""
    e, layout = escape, doc.layout
    head = [f"<h1>{e(doc.name.text)}</h1>", *(f"<p>{e(line.text)}</p>" for line in doc.intro)]
    main: list[str] = []
    side: list[str] = []
    for section in doc.sections:
        parts = side if section.title in layout.side else main
        if section.title:
            parts.append(f"<h2>{e(section.title)}</h2>")
        for entry in section.entries:
            if entry.heading:
                parts.append(f"<h3>{e(entry.heading.text)}</h3>")
            if entry.paragraph:
                parts.append(f"<p>{e(entry.paragraph.text)}</p>")
            if entry.bullets:
                parts.append("<ul>" + "".join(f"<li>{e(b.text)}</li>" for b in entry.bullets) + "</ul>")
    columns = f"<div class='main'>{''.join(main)}</div>" + (f"<div class='side'>{''.join(side)}</div>" if side else "")
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(doc.name.text)} - {e(doc.label)}</title>"
        f"<style>{document_css(style, layout, _ATS_CSS + extra_css)}</style></head>"
        f"<body><header class='{layout.header}'>{''.join(head)}</header><div class='cols'>{columns}</div></body></html>"
    )


class HtmlRenderer:
    format = "html"
    extension = "html"
    media_type = "text/html"

    def render(self, doc: Document, style: Style) -> bytes:
        return html_page(doc, style).encode()
