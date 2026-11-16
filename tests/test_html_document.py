"""The stored HTML of a saved document and the reader that turns it back into a Document."""

import re
import string

from hypothesis import given, strategies as st

from career_buddy.adapters.outputs.render_html import stored_html
from career_buddy.adapters.outputs.render_text import TextRenderer
from career_buddy.adapters.readers.html_document import read_document, read_slots
from career_buddy.domain.document import Document, Entry, Line, Origin, Section, Style
from samples import sample_document

texts = st.text(st.characters(blacklist_categories=("Cs", "Cc")), max_size=30).map(lambda s: " ".join(s.split())).filter(bool)
lines = st.builds(
    Line, texts, st.none() | st.text(string.hexdigits, min_size=1, max_size=32), st.sampled_from(list(Origin)))
entries = st.builds(
    Entry, st.none() | lines, st.none() | lines, st.lists(lines, max_size=3).map(tuple)).filter(lambda e: bool(e.lines()))
titled = st.lists(st.builds(Section, texts, st.lists(entries, max_size=3).map(tuple)), max_size=3).map(tuple)
untitled = st.lists(entries, min_size=1, max_size=4).map(lambda es: (Section("", tuple(es)),))  # a letter's one untitled section
documents = st.builds(Document, lines, st.lists(lines, max_size=3).map(tuple), titled | untitled)


def everything(doc: Document) -> list[tuple[str, str | None, Origin]]:
    rows = [doc.name, *doc.intro, *(line for s in doc.sections for e in s.entries for line in e.lines())]
    return [(line.text, line.source_fact_id, line.origin) for line in rows]


@given(documents)
def test_a_document_survives_being_stored_and_read_back(doc: Document) -> None:
    back = read_document(stored_html(doc))
    assert everything(back) == everything(doc)
    assert back.headings() == doc.headings()
    assert TextRenderer().render(back, Style()) == TextRenderer().render(doc, Style())  # what a download shows is unchanged


@given(documents)
def test_stored_html_uses_only_the_allowed_tags_and_unique_slots(doc: Document) -> None:
    html = stored_html(doc)
    assert set(re.findall(r"</?([a-z0-9]+)", html)) <= {"h1", "h2", "h3", "p", "ul", "li", "strong", "em", "br"}
    slots = re.findall(r'data-slot="([^"]+)"', html)
    assert len(slots) == len(set(slots)) == len(everything(doc))


def test_a_line_shown_from_a_fact_is_an_empty_slot_and_fixed_wording_is_its_placeholder() -> None:
    doc = Document(Line("Ada", "p1", field="title"), (), (
        Section("Experience", (Entry(Line("Analyst", "j1", field="heading"), None, (Line("Did a thing", "a1", field="title"),)),)),
        Section("", (Entry(paragraph=Line("Dear Sir,", "p1", Origin.BOILERPLATE, "greeting")),))))
    assert stored_html(doc).splitlines() == [
        '<h1 data-slot="name" data-fact-id="p1" data-field="title" data-origin="fact"></h1>',
        '<h2 data-origin="boilerplate">Experience</h2>',  # section titles are fixed, not slots
        '<h3 data-slot="heading:j1" data-fact-id="j1" data-field="heading" data-origin="fact"></h3>',
        '<ul><li data-slot="bullet:a1" data-fact-id="a1" data-field="title" data-origin="fact"></li></ul>',
        '<p data-slot="greeting" data-fact-id="p1" data-field="greeting" data-origin="boilerplate">Dear Sir,</p>',
    ]
    assert [s.placeholder for s in read_slots(stored_html(doc))] == ["", "", "", "Dear Sir,"]


def test_the_text_of_each_slot_comes_from_the_resolved_texts_and_overrides_count_as_the_users_own_words() -> None:
    html = stored_html(sample_document())
    back = read_document(html, {"name": "  Jane   Q. Doe "}, frozenset({"name"}))
    assert back.name == Line("Jane Q. Doe", sample_document().name.source_fact_id, Origin.USER)
    assert read_slots(html)[0].id == "name"


def test_markup_outside_the_allowlist_never_reaches_the_document() -> None:
    html = '<h1>Ada</h1><script>alert(1)</script><style>p{}</style><p>Hello <strong>bold</strong><br>there <img src=x></p>'
    doc = read_document(html)
    assert doc.lines() == ["Ada", "Hello bold there"]


def test_hostile_text_is_data_not_markup() -> None:
    doc = Document(Line("<script>x</script> & <b>"), (Line("a < b &amp; c"),))
    assert read_document(stored_html(doc)).lines() == doc.lines()
    assert "<script>" not in stored_html(doc)
