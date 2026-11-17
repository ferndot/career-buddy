"""Renders a Document as DOCX with built-in styles. No tables, text boxes or images; header and footer stay empty.

The template's header is kept (centered, or a shaded band); a side column is not: it would need a table, which an ATS
reads badly, so its sections stay in one column, after the main ones."""

from __future__ import annotations

import io

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from career_buddy.domain.document import Document, Layout, Style

MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_FONTS = {"sans": "Calibri", "serif": "Times New Roman"}
_PAPER = {"letter": (Inches(8.5), Inches(11)), "a4": (Inches(8.27), Inches(11.69))}
_SIZES = {"Normal": 11, "Title": 20, "Heading 1": 13, "List Bullet": 11}


def _set_font(style: object, name: str, size: int) -> None:
    font = style.font  # type: ignore[attr-defined]
    font.name, font.size = name, Pt(size)
    font.color.rgb = RGBColor(0, 0, 0)
    rfonts = style.element.rPr.rFonts  # type: ignore[attr-defined]
    for attr in [a for a in rfonts.attrib if "Theme" in a]:  # theme fonts would override the name
        del rfonts.attrib[attr]


_BAND = "1F3A5F"


def _head(out: object, text: str, layout: Layout, style: str | None = None) -> None:
    """A line of the header, laid out as the template says."""
    p = out.add_paragraph(text, style=style)  # type: ignore[attr-defined]
    if layout.header == "centered":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif layout.header == "band":
        shade = OxmlElement("w:shd")
        shade.set(qn("w:val"), "clear")
        shade.set(qn("w:fill"), _BAND)
        p._p.get_or_add_pPr().append(shade)
        for run in p.runs:
            run.font.color.rgb = RGBColor(255, 255, 255)


class DocxRenderer:
    format = "docx"
    extension = "docx"
    media_type = MEDIA_TYPE

    def render(self, doc: Document, style: Style) -> bytes:
        out = DocxDocument()
        for name, size in _SIZES.items():
            _set_font(out.styles[name], _FONTS[style.font], size)
        section = out.sections[0]
        section.page_width, section.page_height = _PAPER[style.paper]
        section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Inches(0.75)
        out.core_properties.author = ""
        out.core_properties.title = f"{doc.name.text} - {doc.label}"

        _head(out, doc.name.text, doc.layout, "Title")
        for line in doc.intro:
            _head(out, line.text, doc.layout)
        for sec in doc.sections:
            if sec.title:
                out.add_paragraph(sec.title, style="Heading 1")
            for entry in sec.entries:
                if entry.heading:
                    out.add_paragraph().add_run(entry.heading.text).bold = True
                if entry.paragraph:
                    out.add_paragraph(entry.paragraph.text)
                for bullet in entry.bullets:
                    out.add_paragraph(bullet.text, style="List Bullet")
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
