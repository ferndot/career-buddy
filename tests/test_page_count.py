"""The page counter reads the PDF export's own render: its page count matches what the person prints. Needs the browser: skipped without Chromium."""

import io

from pdfminer.high_level import extract_pages

from career_buddy.adapters.outputs.page_count import PdfPageCounter
from career_buddy.adapters.outputs.render_pdf import PdfRenderer
from career_buddy.domain.document import Document, Entry, Line, Section, Style
from test_pdf import FIXTURE

SHORT = Document(Line("Jane Doe"), (), (Section("Experience", (Entry(heading=Line("Engineer, Acme"), bullets=(Line("Cut build times by 60%"),)),)),))


def test_a_long_resume_counts_its_pages_as_the_pdf_export_prints_them(chromium) -> None:
    counted = PdfPageCounter().pages(FIXTURE, Style())
    assert counted.count == len(list(extract_pages(io.BytesIO(PdfRenderer().render(FIXTURE, Style()))))) >= 2
    assert 0 < counted.last_fill <= 1 and counted.lines_per_page > 10


def test_a_short_resume_is_one_page_and_mostly_empty(chromium) -> None:
    counted = PdfPageCounter().pages(SHORT, Style())
    assert counted.count == 1 and counted.last_fill < 0.25 and counted.lines_per_page >= 3
