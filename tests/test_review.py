"""The validation of a model's review of a job posting: pure properties and the cases the keyword pass got wrong."""

import re

from hypothesis import given, strategies as st

from career_buddy.domain.review import MAX_MUST, MAX_NICE, Review, uncovered, validate

words = st.sampled_from(["python", "Kubernetes", "SQL", "team", "policy", "Acme", "Engineer", "ecosystem", "5+", "x", "go", "C++", "u.s", "Rust"])
phrases = st.lists(words, min_size=1, max_size=3).map(" ".join)
terms = st.lists(st.one_of(phrases, st.text(max_size=8)), max_size=30)
postings = st.lists(words, min_size=1, max_size=40).map(" ".join)


def reviewed(posting: str, must: list[str], nice: list[str], title: str = "Engineer", company: str = "Acme") -> Review:
    return validate(Review(title, company, tuple(must), tuple(nice)), posting)


@given(postings, terms, terms)
def test_every_kept_term_is_in_the_posting_and_none_is_a_name_a_fragment_or_a_repeat(posting: str, must: list[str], nice: list[str]) -> None:
    out = reviewed(posting, must, nice)
    kept = [*out.must_have, *out.nice_to_have]
    low = [t.lower() for t in kept]
    assert all(t.lower() in posting.lower() for t in kept)
    assert not {"acme", "engineer"} & set(low)
    assert all(len(t) >= 2 and re.search("[A-Za-z]", t) for t in kept)
    assert len(set(low)) == len(low)
    assert len(out.must_have) <= MAX_MUST and len(out.nice_to_have) <= MAX_NICE


@given(postings, terms)
def test_a_term_is_kept_whatever_the_postings_case_and_keeps_the_models_spelling(posting: str, must: list[str]) -> None:
    shouted = reviewed(posting.upper(), must, [])
    plain = reviewed(posting, must, [])
    assert [t.lower() for t in shouted.must_have] == [t.lower() for t in plain.must_have]
    assert set(plain.must_have) <= {" ".join(t.split()) for t in must}


@given(postings, terms)
def test_validating_twice_changes_nothing(posting: str, must: list[str]) -> None:
    once = reviewed(posting, must, must)
    assert validate(once, posting) == once


def test_the_fragments_in_the_screenshot_are_all_dropped() -> None:
    posting = "Anthropic's policy team builds applications for the enterprise ecosystem in the U.S. and the sciences. Kubernetes required."
    junk = ["Anthropic", "Anthropic's", "policy", "enterprise", "applications", "ecosystem", "sciences"]
    assert reviewed(posting, [*junk, "Kubernetes"], [], title="Policy Lead", company="Anthropic").must_have == ("Kubernetes",)


def test_a_term_is_matched_as_a_whole_word() -> None:
    assert reviewed("We use JavaScript daily", ["Java", "JavaScript"], []).must_have == ("JavaScript",)


def test_a_must_have_is_not_repeated_as_nice_to_have_and_the_company_is_dropped_from_both() -> None:
    out = reviewed("Rust and SQL at Acme", ["Rust", "Acme"], ["rust", "SQL", "ACME"])
    assert (out.must_have, out.nice_to_have) == (("Rust",), ("SQL",))


@given(st.lists(st.sampled_from(["python", "sql", "kubernetes", "rust"]), min_size=1, max_size=4, unique=True))
def test_a_term_made_of_words_the_facts_use_is_covered(skills: list[str]) -> None:
    asked = [f"5+ years of {s}" for s in skills]
    assert uncovered(asked, [", ".join(skills)]) == ()
    assert uncovered(asked, []) == tuple(asked)


def test_a_term_with_one_word_no_fact_uses_is_uncovered() -> None:
    assert uncovered(["security clearance", "Kubernetes"], ["Kubernetes", "Security engineer"]) == ("security clearance",)
