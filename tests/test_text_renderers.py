"""Markdown, HTML and TXT renderers (stdlib only)."""

from career_graph.adapters.outputs.render_html import HtmlRenderer
from career_graph.adapters.outputs.render_markdown import MarkdownRenderer
from career_graph.adapters.outputs.render_text import TextRenderer
from career_graph.domain.document import Document, Entry, Line, Section, Style
from samples import sample_document

STYLE = Style()


def test_markdown_matches_the_v1_layout() -> None:
    md = MarkdownRenderer().render(sample_document(), STYLE).decode()
    assert md.startswith("# Jane Doe\n\nLisbon, Portugal\n\nPlatform engineer\n\n## Summary\nBuilds data pipelines\n")
    assert "### Senior Engineer, Acme Corp (Mar 2019 - Jan 2023)\n- Cut build times by 60%\n\n" in md
    assert "## Education\n- BSc Computer Science, University of Lisbon\n\n## Skills\nPython, Kubernetes\n" in md


def test_text_uses_plain_headings_and_dash_bullets() -> None:
    txt = TextRenderer().render(sample_document(), STYLE).decode()
    assert txt.startswith("Jane Doe\nLisbon, Portugal\nPlatform engineer\n\nSummary\nBuilds data pipelines\n\nExperience\n")
    assert "Senior Engineer, Acme Corp (Mar 2019 - Jan 2023)\n- Cut build times by 60%\n" in txt


def test_html_is_single_column_and_escapes_text() -> None:
    doc = Document(Line("A <b> & C"), sections=(Section("Experience", (Entry(heading=Line("x"), bullets=(Line("1 < 2"),)),)),))
    html = HtmlRenderer().render(doc, STYLE).decode()
    assert "<h1>A &lt;b&gt; &amp; C</h1>" in html
    assert "<h2>Experience</h2>" in html and "<li>1 &lt; 2</li>" in html
    assert "<table" not in html and "<img" not in html


def test_renderers_declare_format_and_media_type() -> None:
    assert (MarkdownRenderer.format, MarkdownRenderer.media_type) == ("markdown", "text/markdown")
    assert (HtmlRenderer.format, HtmlRenderer.media_type) == ("html", "text/html")
    assert (TextRenderer.format, TextRenderer.media_type) == ("txt", "text/plain")
