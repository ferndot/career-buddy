"""AI-marker cleaning: the exact changes it reports and what clean_document touches."""

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.markers import Change, clean, clean_document


def test_a_swap_reports_what_was_found_and_what_replaced_it() -> None:
    text, changes = clean("Delve into it", Origin.USER)
    assert (text, changes) == ("Explore it", [Change("swap", "Delve into", "Explore")])


def test_an_artifact_is_reported_with_an_empty_replacement() -> None:
    assert clean("Cut **costs**", Origin.USER)[1] == [Change("strip", "**"), Change("strip", "**")]


def test_a_dash_in_llm_text_is_reported_as_a_swap_to_a_comma() -> None:
    assert clean("a — b", Origin.SUGGESTION) == ("a, b", [Change("swap", "—", ", ")])


def test_each_em_dash_in_user_text_is_flagged_by_name() -> None:
    assert clean("a — b — c", Origin.USER)[1] == [Change("flag", "—"), Change("flag", "—")]


def test_clean_document_cleans_the_name_and_intro_and_drops_blank_paragraphs() -> None:
    doc = Document(
        Line("Jane **Doe**", "p"),
        (Line("Delve into London", "p"),),
        (Section("Experience", (Entry(Line("Delves into data", "h"), Line("  ", "x"), (Line("ok", "b"),)),)),),
    )
    cleaned, changes = clean_document(doc)
    assert cleaned.name == Line("Jane Doe", "p")
    assert cleaned.intro == (Line("Explore London", "p"),)
    assert cleaned.sections[0].entries == (Entry(Line("Explores data", "h"), None, (Line("ok", "b"),)),)
    assert [(c.kind, c.source_fact_id) for c in changes] == [("strip", "p"), ("strip", "p"), ("swap", "p"), ("swap", "h")]


def test_clean_document_keeps_a_paragraph_with_text() -> None:
    doc = Document(Line("J"), (), (Section("", (Entry(paragraph=Line("Hi there", "a")),)),))
    assert clean_document(doc)[0].sections[0].entries[0].paragraph == Line("Hi there", "a")
