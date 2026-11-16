"""AI-marker cleaning: pure, applied at render time only."""

from hypothesis import given, strategies as st

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.markers import clean, clean_document

USER, LLM = Origin.USER, Origin.SUGGESTION


def test_user_text_swaps_only_delve_into_and_in_the_realm_of_and_marks_them_weak() -> None:
    text, changes = clean("Delve into logs, then in the realm of data", USER)
    assert text == "Explore logs, then in data"
    assert {c.kind for c in changes} == {"swap"} and all(c.weak for c in changes)


def test_other_weak_swap_words_are_only_flagged_in_user_text() -> None:
    text, changes = clean("Showcasing results; the tapestry underscores it", USER)
    assert text == "Showcasing results; the tapestry underscores it"
    assert [(c.kind, c.found, c.weak) for c in changes] == [
        ("flag", "Showcasing", True), ("flag", "tapestry", True), ("flag", "underscores", True)]


def test_llm_text_swaps_every_weak_swap_word_with_case_kept() -> None:
    text, changes = clean("Showcasing results; the tapestry underscores it, in the realm of data", LLM)
    assert text == "Showing results; the mix highlights it, in data"
    assert {c.kind for c in changes} == {"swap"}


def test_words_with_no_source_are_left_alone_in_both_kinds_of_text() -> None:
    said = "Utilize the critical landscape to leverage it in today's fast-paced world"
    for origin in (USER, LLM):
        assert clean(said, origin) == (said, [])


def test_zero_width_characters_and_chatbot_artifacts_are_stripped() -> None:
    text, changes = clean("Certainly! Here's Cut​ costs **by** 5% As an AI language model", USER)
    assert text == "Cut costs by 5%"
    assert {c.kind for c in changes} == {"strip"}


def test_ambiguous_words_are_weak_flags_and_kept_in_user_text() -> None:
    said = "Fixed an intricate bug and potential findings"
    text, changes = clean(said, USER)
    assert text == said
    assert [(c.kind, c.found, c.weak) for c in changes] == [
        ("flag", "intricate", True), ("flag", "potential", True), ("flag", "findings", True)]


def test_ambiguous_words_are_flag_only_in_llm_text() -> None:
    text, changes = clean("Fixed an intricate bug", LLM)
    assert text == "Fixed an intricate bug" and [c.kind for c in changes] == ["flag"]


def test_only_artifact_strips_are_not_weak_signals() -> None:
    assert [c.weak for c in clean("Cut **it**", USER)[1]] == [False, False]
    assert all(c.weak for c in clean("a — b", USER)[1] + clean("a — b", LLM)[1])


def test_em_dash_is_flagged_in_user_text_and_replaced_in_llm_text() -> None:
    user_text, user_changes = clean("Led teams — and shipped", USER)
    assert user_text == "Led teams — and shipped" and [c.kind for c in user_changes] == ["flag"]
    llm_text, llm_changes = clean("Led teams — and shipped", LLM)
    assert llm_text == "Led teams, and shipped" and [c.kind for c in llm_changes] == ["swap"]


def test_clean_document_cleans_every_line_by_origin_and_reports_the_source() -> None:
    doc = Document(
        Line("Jane"),
        sections=(Section("Experience", (Entry(bullets=(
            Line("Delve into data", "a1"), Line("​", "a2"), Line("Ran a — test", "a3", Origin.SUGGESTION),
        )),)),),
    )
    cleaned, changes = clean_document(doc)
    assert [b.text for b in cleaned.sections[0].entries[0].bullets] == ["Explore data", "Ran a, test"]
    assert {(c.kind, c.source_fact_id) for c in changes} == {("swap", "a1"), ("strip", "a2"), ("swap", "a3")}


FRAGMENTS = ["delve into", "Delved into", "potential", "tapestry", "in the realm of", "findings", "intricate", "—",
             "​", "**", "As an AI language model", "Certainly! Here's", " ", "5", "60%", "x", "Showcasing",
             "critical", "underscores", "*", "​*", "Certainly!", "Here's"]
texts = st.lists(st.one_of(st.sampled_from(FRAGMENTS), st.text(max_size=6)), max_size=12).map("".join)
origins = st.sampled_from([Origin.FACT, Origin.USER, Origin.SUGGESTION, Origin.BOILERPLATE])


@given(texts, origins)
def test_clean_is_idempotent(text: str, origin: Origin) -> None:
    once, _ = clean(text, origin)
    assert clean(once, origin)[0] == once


@given(texts, origins)
def test_clean_never_changes_digits(text: str, origin: Origin) -> None:
    assert [c for c in clean(text, origin)[0] if c.isdigit()] == [c for c in text if c.isdigit()]
