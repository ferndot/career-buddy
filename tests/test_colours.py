"""A template's colours, defined once on its Layout, reach every format that can carry colour (html, pdf, docx; text and markdown cannot)."""

import io

import pytest
from docx import Document as DocxDocument
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTRect

from career_buddy.adapters.outputs.render_docx import DocxRenderer
from career_buddy.adapters.outputs.render_html import HtmlRenderer
from career_buddy.adapters.outputs.render_pdf import PdfRenderer
from career_buddy.domain.document import Style
from career_buddy.domain.templates import NAVY, PANEL, STEEL, TEMPLATES, build_document, get_template
from samples import PROFILE


def doc(template: str):
    return build_document(PROFILE, get_template(template))


def rgb(hex_colour: str) -> tuple[float, ...]:
    return tuple(int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))


@pytest.mark.parametrize("spec", TEMPLATES, ids=lambda s: s.id)
def test_every_colour_in_a_templates_css_is_one_of_its_layout_colours(spec) -> None:
    html = HtmlRenderer().render(doc(spec.id), Style()).decode() if spec.kind == "resume" else ""
    for colour in (spec.layout.accent, spec.layout.panel):
        assert not colour or colour in spec.layout.css  # the css is written from the same constants
        assert not html or not colour or colour in html


def test_the_html_carries_the_accent_and_the_panel() -> None:
    sidebar = HtmlRenderer().render(doc("resume-sidebar"), Style()).decode()
    assert f"h2{{color:{STEEL}" in sidebar and f"background:{PANEL}" in sidebar
    modern = HtmlRenderer().render(doc("resume-modern"), Style()).decode()
    assert f"header{{background:{NAVY}" in modern and f"h2{{color:{NAVY}" in modern
    assert "#1f3a5f" not in HtmlRenderer().render(doc("resume-classic"), Style()).decode()  # classic is black on white


def test_the_docx_band_and_headings_use_the_templates_accent() -> None:
    out = DocxDocument(io.BytesIO(DocxRenderer().render(doc("resume-modern"), Style())))
    assert str(out.styles["Heading 1"].font.color.rgb) == NAVY[1:].upper()
    assert f'w:fill="{NAVY[1:].upper()}"' in out.paragraphs[0]._p.xml
    plain = DocxDocument(io.BytesIO(DocxRenderer().render(doc("resume-classic"), Style())))
    assert str(plain.styles["Heading 1"].font.color.rgb) == "000000"


def fills(pdf: bytes) -> set[tuple[float, ...]]:
    found: set[tuple[float, ...]] = set()
    for page in extract_pages(io.BytesIO(pdf)):
        found |= {tuple(round(c, 2) for c in el.non_stroking_color) for el in page if isinstance(el, LTRect) and isinstance(el.non_stroking_color, tuple)}
    return found


def test_the_pdf_prints_the_background_colours(chromium) -> None:
    """Chromium leaves backgrounds out of a print unless asked: the band would be white, under white text."""
    assert tuple(round(c, 2) for c in rgb(NAVY)) in fills(PdfRenderer().render(doc("resume-modern"), Style()))
    assert tuple(round(c, 2) for c in rgb(PANEL)) in fills(PdfRenderer().render(doc("resume-sidebar"), Style()))
