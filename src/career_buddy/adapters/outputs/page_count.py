"""Counts the pages a document prints on, and how full the last one is: the PDF export's own render (same HTML, CSS, paper and margins),
read back with pdfminer. DOCX pagination is not measured and can differ in Word."""

from __future__ import annotations

import io
from collections.abc import Iterator

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTContainer, LTTextLine

from career_buddy.adapters.outputs.render_pdf import PdfRenderer
from career_buddy.domain.coverage import Pages
from career_buddy.domain.document import Document, Style

MARGIN = 54.0  # points: the 0.75in the PDF renderer prints with


def _lines(node: object) -> Iterator[LTTextLine]:
    if isinstance(node, LTTextLine):
        if node.get_text().strip():
            yield node
    elif isinstance(node, LTContainer):
        for child in node:
            yield from _lines(child)


class PdfPageCounter:
    def __init__(self, renderer: PdfRenderer | None = None) -> None:
        self._renderer = renderer or PdfRenderer()

    def pages(self, doc: Document, style: Style) -> Pages:
        """RendererUnavailable: Chromium is not installed."""
        pages = list(extract_pages(io.BytesIO(self._renderer.render(doc, style)), laparams=LAParams(boxes_flow=0.5)))
        last = list(_lines(pages[-1])) if pages else []
        printable = pages[-1].height - 2 * MARGIN if pages else 1.0
        fill = (pages[-1].height - MARGIN - min(line.y0 for line in last)) / printable if last else 0.0
        return Pages(max(len(pages), 1), min(max(fill, 0.0), 1.0), len(list(_lines(pages[0]))) if pages else 0)
