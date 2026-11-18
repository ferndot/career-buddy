"""Every template, rendered to PDF and read back with the app's reader: reading order, tagging, and the ats_safe claim."""

import pytest

from career_buddy.adapters.outputs.render_pdf import PdfRenderer
from career_buddy.adapters.readers.pdf_text import PdfTextReader
from career_buddy.domain.ats import check
from career_buddy.domain.document import Style
from career_buddy.domain.templates import TEMPLATES, build_document
from samples import PROFILE


def measured(spec):
    doc = build_document(PROFILE, spec)
    pdf = PdfRenderer().render(doc, Style())
    return doc, pdf, PdfTextReader().read(pdf)


def words(lines) -> list[str]:
    return " ".join(lines).split()


@pytest.mark.parametrize("spec", TEMPLATES, ids=lambda s: s.id)
def test_the_pdf_reads_back_in_document_order_once_and_is_tagged(chromium, spec) -> None:
    doc, pdf, got = measured(spec)
    assert words(got.lines) == words(doc.lines())  # main column before the side column, every line exactly once
    assert b"/StructTreeRoot" in pdf and b"/MarkInfo" in pdf


@pytest.mark.parametrize("spec", TEMPLATES, ids=lambda s: s.id)
def test_a_template_marked_ats_safe_passes_every_check(chromium, spec) -> None:
    doc, _, got = measured(spec)
    if spec.ats_safe:
        assert check(doc, got) == []
