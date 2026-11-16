"""DOCX renderer (inspected with python-docx) and DOCX reader (fed crafted files)."""

import io
import zipfile

import pytest
from docx import Document as DocxDocument
from docx.oxml import parse_xml
from docx.shared import Inches

from career_buddy.adapters.outputs.render_docx import DocxRenderer
from career_buddy.adapters.readers.docx_text import DocxTextReader
from career_buddy.application.ports import UnreadableDocument
from career_buddy.domain.document import Style
from samples import sample_document

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def render(style: Style = Style()) -> DocxDocument:
    return DocxDocument(io.BytesIO(DocxRenderer().render(sample_document(), style)))


def test_docx_uses_builtin_styles_in_reading_order() -> None:
    paragraphs = [(p.style.name, p.text) for p in render().paragraphs]
    assert paragraphs[0] == ("Title", "Jane Doe")
    assert ("Heading 1", "Experience") in paragraphs
    assert ("List Bullet", "Cut build times by 60%") in paragraphs
    assert [t for _, t in paragraphs] == sample_document().lines()


def test_docx_is_ats_safe_by_construction() -> None:
    doc = render()
    body = doc.element.body
    assert not doc.tables
    for tag in ("w:tbl", "w:txbxContent", "w:drawing", "w:pict"):
        assert not body.xpath(f".//{tag}")
    section = doc.sections[0]
    assert section.header.is_linked_to_previous and section.footer.is_linked_to_previous
    assert section.left_margin >= Inches(0.5) and section.top_margin >= Inches(0.5)
    assert (section.page_width, section.page_height) == (Inches(8.5), Inches(11))


def test_docx_font_and_paper_follow_the_style() -> None:
    doc = render(Style(font="serif", paper="a4"))
    assert doc.styles["Normal"].font.name == "Times New Roman"
    assert doc.styles["Normal"].font.size.pt == 11
    assert doc.styles["Heading 1"].font.name == "Times New Roman"
    assert abs(doc.sections[0].page_width.cm - 21.0) < 0.05


def test_reader_returns_the_rendered_lines_with_no_structure_flags() -> None:
    extracted = DocxTextReader().read(DocxRenderer().render(sample_document(), Style()))
    assert extracted.lines == sample_document().lines()
    assert not (extracted.has_tables or extracted.has_text_boxes or extracted.header_footer_text)
    assert extracted.image_count == 0


def test_reader_reports_table_text_box_and_header() -> None:
    doc = DocxDocument()
    doc.add_paragraph("Body line")
    doc.add_table(rows=1, cols=2).cell(0, 0).text = "In a table"
    doc.sections[0].header.paragraphs[0].text = "jane@example.com"
    doc.paragraphs[0]._p.append(parse_xml(
        f'<w:r xmlns:w="{W}" xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape><v:textbox>'
        '<w:txbxContent><w:p><w:r><w:t>Boxed</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r>'
    ))
    buf = io.BytesIO()
    doc.save(buf)
    extracted = DocxTextReader().read(buf.getvalue())
    assert extracted.has_tables and extracted.has_text_boxes
    assert extracted.header_footer_text == "jane@example.com"
    assert extracted.image_count == 1
    assert {"Body line", "In a table", "Boxed"} <= set(extracted.lines)


def test_reader_rejects_non_docx_bytes() -> None:
    with pytest.raises(UnreadableDocument):
        DocxTextReader().read(b"not a zip")


def test_reader_rejects_a_zip_bomb_before_opening() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"\0" * (51 * 1024 * 1024))
    with pytest.raises(UnreadableDocument, match="too large"):
        DocxTextReader().read(buf.getvalue())
