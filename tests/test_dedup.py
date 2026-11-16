"""Duplicate candidates: pure, symmetric, and never a fact with itself."""

import random

import pytest
from hypothesis import given, strategies as st

from career_buddy.domain.dedup import merge_candidates, normalize_org
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Acme Corp.", "acme"), ("ACME, Inc", "acme"), ("Acme Corporation", "acme"), ("Müller GmbH", "müller"),
     ("Foo & Bar Co., Ltd.", "foo bar"), ("Globex", "globex")],
)
def test_normalize_org(raw: str, expected: str) -> None:
    assert normalize_org(raw) == expected


def org(id: str, name: str) -> Fact:
    return Fact(id, FactKind.ORGANIZATION, name)


def pairs(batch: FactBatch) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b, _ in merge_candidates(batch)}


def test_suffix_variants_are_one_employer_and_distinct_names_are_not() -> None:
    batch = FactBatch((org("1", "Acme Corp"), org("2", "Acme"), org("3", "Globex"), org("4", "Acme Labs")))
    assert pairs(batch) == {frozenset("12")}


def test_close_spelling_passes_the_threshold_and_distant_does_not() -> None:
    assert pairs(FactBatch((org("1", "Initech Systems"), org("2", "Initech Systems")))) == {frozenset("12")}
    assert pairs(FactBatch((org("1", "Initech Systems"), org("2", "Initech Systemz")))) == {frozenset("12")}  # 0.93
    assert pairs(FactBatch((org("1", "Anthropic"), org("2", "Anthropik")))) == set()  # 0.89, just under
    assert pairs(FactBatch((org("1", "Anthropic"), org("2", "Antropic Labs")))) == set()


def positions_batch(a_org: str, b_org: str, a_dates: dict, b_dates: dict, b_title: str = "engineer") -> FactBatch:
    facts = (
        org("o1", "Acme Corp"), org("o2", "Acme"), org("o3", "Globex"),
        Fact("p1", FactKind.POSITION, "Senior Engineer", a_dates),
        Fact("p2", FactKind.POSITION, b_title, b_dates),
    )
    return FactBatch(facts, (Link("p1", a_org, LinkKind.AT), Link("p2", b_org, LinkKind.AT)))


def test_positions_pair_when_title_org_and_dates_agree() -> None:
    batch = positions_batch("o1", "o2", {"started": "Mar 2019", "finished": "Jan 2023"}, {"started": "2020", "finished": "2021"},
                            "Senior  ENGINEER")
    assert frozenset(("p1", "p2")) in pairs(batch)


@pytest.mark.parametrize(
    ("b_org", "b_dates", "b_title"),
    [("o3", {"started": "2020", "finished": "2021"}, "Senior Engineer"),  # other employer
     ("o2", {"started": "2024", "finished": "2025"}, "Senior Engineer"),  # no date overlap
     ("o2", {"started": "2020", "finished": "2021"}, "Junior Engineer")],  # other title
)
def test_positions_do_not_pair_otherwise(b_org, b_dates, b_title) -> None:
    batch = positions_batch("o1", b_org, {"started": "Mar 2019", "finished": "Jan 2023"}, b_dates, b_title)
    assert frozenset(("p1", "p2")) not in pairs(batch)


def test_positions_under_one_merged_org_pair_and_open_ended_dates_overlap() -> None:
    batch = positions_batch("o1", "o1", {"started": "Mar 2019"}, {"started": "2024", "finished": "present"}, "Senior Engineer")
    assert frozenset(("p1", "p2")) in pairs(batch)


def test_hidden_facts_are_never_proposed() -> None:
    hidden = Fact("2", FactKind.ORGANIZATION, "Acme", {"hidden": "true"})
    assert pairs(FactBatch((org("1", "Acme Corp"), hidden))) == set()


names = st.text(alphabet="abcde ,.", min_size=1, max_size=6)
orgs = st.lists(st.builds(org, st.sampled_from("abcdef"), names), max_size=6)


@given(orgs, st.randoms(use_true_random=False))
def test_candidates_are_symmetric_and_never_self_pairs(facts, rnd: random.Random) -> None:
    shuffled = list(facts)
    rnd.shuffle(shuffled)
    forward, backward = merge_candidates(FactBatch(tuple(facts))), merge_candidates(FactBatch(tuple(shuffled)))
    assert all(a != b for a, b, _ in forward)
    # Duplicate ids in the input: the later fact wins in both orders, so compare only when ids are unique.
    if len({f.id for f in facts}) == len(facts):
        assert {(frozenset((a, b)), s) for a, b, s in forward} == {(frozenset((a, b)), s) for a, b, s in backward}


def test_a_position_with_only_an_end_year_does_not_run_to_the_present() -> None:
    batch = positions_batch("o1", "o1", {"finished": "2015"}, {"started": "2024", "finished": "present"}, "Senior Engineer")
    assert frozenset(("p1", "p2")) not in pairs(batch)
