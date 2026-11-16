"""Reads a DOCX back to text and structure: body, tables, text boxes, headers and footers."""

from __future__ import annotations

import io
import zipfile

from docx import Document as DocxDocument
from docx.oxml.ns import qn

from career_buddy.application.ports import UnreadableDocument
from career_buddy.domain.ats import Extracted

MAX_UNCOMPRESSED = 50 * 1024 * 1024  # zip-bomb guard, checked before python-docx opens anything


def _text(paragraph: object) -> str:
    """Text of one paragraph, leaving out the paragraphs nested inside its text boxes."""
    p_tag = qn("w:p")

    def owner(node: object) -> object:
        while node.tag != p_tag:  # type: ignore[attr-defined]
            node = node.getparent()  # type: ignore[attr-defined]
        return node

    return "".join(t.text or "" for t in paragraph.iter(qn("w:t")) if owner(t) is paragraph)  # type: ignore[attr-defined]


class DocxTextReader:
    def read(self, data: bytes) -> Extracted:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED:
                    raise UnreadableDocument("DOCX is too large when uncompressed")
            doc = DocxDocument(io.BytesIO(data))
        except (zipfile.BadZipFile, KeyError, ValueError) as error:
            raise UnreadableDocument(f"Not a readable DOCX: {error}") from error

        body = doc.element.body
        lines = [t.strip() for p in body.iter(qn("w:p")) if (t := _text(p)).strip()]
        parts = []
        for section in doc.sections:
            for part in (section.header, section.footer):
                if not part.is_linked_to_previous:
                    parts += [p.text.strip() for p in part.paragraphs if p.text.strip()]
        return Extracted(
            text="\n".join(lines),
            lines=lines,
            has_tables=any(True for _ in body.iter(qn("w:tbl"))),
            has_text_boxes=any(True for _ in body.iter(qn("w:txbxContent"))),
            header_footer_text="\n".join(parts),
            image_count=sum(1 for tag in ("w:drawing", "w:pict") for _ in body.iter(qn(tag))),
        )
