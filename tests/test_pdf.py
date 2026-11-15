"""PDF renderer (Playwright, Chromium print) and PDF reader (pdfminer.six).

The fixture check at the bottom is the PDF engine gate: text extracted from our own PDF must contain every
expected line, in order. Tests that need a browser use the `chromium` fixture and skip when it is missing.
"""

import io
import re

import pytest
from pdfminer.high_level import extract_pages

from career_graph.adapters.outputs.render_pdf import PdfRenderer
from career_graph.adapters.readers.pdf_text import PdfTextReader
from career_graph.application.ports import NoTextLayer, RendererUnavailable, UnreadableDocument
from career_graph.domain.document import Document, Entry, Line, Section, Style
from samples import sample_document

LONG = (
    "Designed, built and operated a multi-region data platform serving 40 internal teams, cutting p99 query "
    "latency by 35% while reducing cloud spend by $120k per year across C++, C# and R&D workloads at Zoë's Café"
)
FIXTURE = Document(
    Line("Zoë Ångström-O'Brien"),
    (Line("Lisbon, Portugal | zoe@example.com | +351 912 345 678"), Line("Platform engineer & researcher")),
    (
        Section("Summary", (Entry(paragraph=Line(LONG)),)),
        Section(
            "Experience",
            tuple(
                Entry(heading=Line(f"Staff Engineer {n}, Acme & Sons (Mar 2019 - Present)"),
                      bullets=tuple(Line(f"{LONG} ({n}.{i})") for i in range(4)))
                for n in range(6)  # long enough to run onto a second page
            ),
        ),
        Section("Skills", (Entry(paragraph=Line("Python, C++, C#, Kubernetes, Postgres")),)),
    ),
)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def pages(pdf: bytes) -> list:
    return list(extract_pages(io.BytesIO(pdf)))


def test_missing_chromium_raises_a_clear_error(tmp_path) -> None:
    with pytest.raises(RendererUnavailable, match="playwright install chromium"):
        PdfRenderer(executable_path=str(tmp_path / "no-chrome.exe")).render(sample_document(), Style())


def test_pdf_has_letter_pages_and_a_text_layer(chromium) -> None:
    pdf = PdfRenderer().render(sample_document(), Style())
    assert pdf.startswith(b"%PDF")
    (page,) = pages(pdf)
    assert (round(page.width), round(page.height)) == (612, 792)


def test_pdf_paper_follows_the_style(chromium) -> None:
    pdf = PdfRenderer().render(sample_document(), Style(paper="a4"))
    page = pages(pdf)[0]
    assert abs(page.width - 595.3) < 2 and abs(page.height - 841.9) < 2


def test_reader_reports_lines_and_no_images(chromium) -> None:
    extracted = PdfTextReader().read(PdfRenderer().render(sample_document(), Style()))
    assert extracted.lines[0] == "Jane Doe"
    assert "Experience" in extracted.lines
    assert extracted.image_count == 0 and extracted.empty_pages == 0
    assert not (extracted.has_tables or extracted.has_text_boxes)


def test_blank_pdf_has_no_text_layer(chromium) -> None:
    pdf = PdfRenderer().render(Document(Line("")), Style())
    with pytest.raises(NoTextLayer):
        PdfTextReader().read(pdf)


def test_reader_rejects_non_pdf_bytes() -> None:
    with pytest.raises(UnreadableDocument):
        PdfTextReader().read(b"definitely not a pdf")


@pytest.mark.parametrize("font", ["sans", "serif"])
def test_pdf_engine_fixture_text_contains_every_expected_line_in_order(chromium, font) -> None:
    pdf = PdfRenderer().render(FIXTURE, Style(font=font))
    assert len(pages(pdf)) >= 2  # the fixture really spans pages
    extracted = normalized(PdfTextReader().read(pdf).text)
    assert "(cid:" not in extracted  # no unmapped glyphs
    position = 0
    for expected in FIXTURE.lines():
        want = normalized(expected)
        found = extracted.find(want, position)
        assert found >= 0, f"missing or out of order: {expected!r}"
        position = found + len(want)
