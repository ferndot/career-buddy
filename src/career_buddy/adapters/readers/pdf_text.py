"""Reads a PDF back to text with pdfminer.six. Reports images; a PDF with no text layer is rejected."""

from __future__ import annotations

import io
from collections.abc import Iterator

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTContainer, LTImage, LTTextContainer
from pdfminer.psparser import PSException

from career_buddy.application.ports import NoTextLayer, UnreadableDocument
from career_buddy.domain.ats import Extracted

MAX_PAGES = 10


def _walk(element: object) -> Iterator[object]:
    if isinstance(element, (LTTextContainer, LTImage)):
        yield element
    elif isinstance(element, LTContainer):
        for child in element:
            yield from _walk(child)


class PdfTextReader:
    def read(self, data: bytes) -> Extracted:
        try:
            pages = list(extract_pages(io.BytesIO(data), laparams=LAParams(boxes_flow=0.5), maxpages=MAX_PAGES))
        except PSException as error:
            raise UnreadableDocument(f"Not a readable PDF: {error}") from error

        lines: list[str] = []
        images = empty_pages = 0
        for page in pages:
            page_lines: list[str] = []
            for node in _walk(page):
                if isinstance(node, LTImage):
                    images += 1
                else:
                    page_lines += [t.strip() for t in node.get_text().splitlines() if t.strip()]  # type: ignore[attr-defined]
            empty_pages += not page_lines
            lines += page_lines
        if not lines:
            raise NoTextLayer("No text layer; OCR is not supported")
        return Extracted(text="\n".join(lines), lines=lines, image_count=images, empty_pages=empty_pages)
