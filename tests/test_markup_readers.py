"""Readers for the text formats: they undo the markup so the ATS check can compare lines."""

from career_buddy.adapters.outputs.render_html import HtmlRenderer
from career_buddy.adapters.outputs.render_markdown import MarkdownRenderer
from career_buddy.adapters.outputs.render_text import TextRenderer
from career_buddy.adapters.readers.markup_text import HtmlTextReader, PlainTextReader
from career_buddy.domain.document import Style
from samples import sample_document

DOC = sample_document()


def test_plain_reader_strips_markdown_and_bullet_markers() -> None:
    for renderer in (MarkdownRenderer(), TextRenderer()):
        extracted = PlainTextReader().read(renderer.render(DOC, Style()))
        assert extracted.lines == DOC.lines()


def test_html_reader_returns_text_and_flags_tables_and_images() -> None:
    assert HtmlTextReader().read(HtmlRenderer().render(DOC, Style())).lines == DOC.lines()
    extracted = HtmlTextReader().read(b"<table><tr><td>a</td></tr></table><img src=x><style>p{}</style>")
    assert extracted.has_tables and extracted.image_count == 1
    assert extracted.lines == ["a"]
