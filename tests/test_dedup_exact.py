"""merge_candidates: date overlap edges, the score threshold, scores and ordering."""

import pytest

from career_buddy.domain.dedup import merge_candidates
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind


def org(id: str, name: str) -> Fact:
    return Fact(id, FactKind.ORGANIZATION, name)


def job(id: str, employer: str | None, title: str = "Engineer", **attrs: str) -> tuple[Fact, tuple[Link, ...]]:
    links = (Link(id, employer, LinkKind.AT),) if employer else ()
    return Fact(id, FactKind.POSITION, title, dict(attrs)), links


def batch(*parts: Fact | tuple[Fact, tuple[Link, ...]]) -> FactBatch:
    facts: list[Fact] = []
    links: list[Link] = []
    for part in parts:
        if isinstance(part, Fact):
            facts.append(part)
        else:
            facts.append(part[0])
            links += part[1]
    return FactBatch(tuple(facts), tuple(links))


def same_job(first: dict[str, str], second: dict[str, str]) -> list[tuple[str, str, float]]:
    return merge_candidates(batch(org("o", "Acme"), job("p1", "o", **first), job("p2", "o", **second)))


@pytest.mark.parametrize(
    ("first", "second", "duplicate"),
    [
        ({"started": "2010", "finished": "2012"}, {"started": "2015", "finished": "2016"}, False),
        ({"started": "2015", "finished": "2016"}, {"started": "2010", "finished": "2012"}, False),
        ({"started": "2010", "finished": "2012"}, {"started": "2012", "finished": "2014"}, True),
        ({"started": "2012", "finished": "2014"}, {"started": "2010", "finished": "2012"}, True),
        ({"started": "2010", "finished": "2012"}, {"started": "2011", "finished": "2013"}, True),
        ({"period": "2010"}, {"period": "2015"}, False),
        ({"period": "2010"}, {"period": "2010"}, True),
        ({"period": "2010 - Present"}, {"period": "2015"}, True),
        ({"period": "2010 - 2012"}, {"period": "- 2008"}, False),
        ({"period": "2010 - 2012"}, {}, True),
    ],
)
def test_positions_are_duplicates_only_when_their_years_overlap(first, second, duplicate) -> None:
    assert bool(same_job(first, second)) is duplicate


def test_a_started_year_alone_runs_to_the_present() -> None:
    assert same_job({"started": "2010"}, {"started": "2020", "finished": "2021"}) != []


def test_the_same_employer_scores_one() -> None:
    assert same_job({}, {}) == [("p1", "p2", 1.0)]


def test_a_position_without_an_employer_is_never_proposed() -> None:
    assert merge_candidates(batch(org("o", "Acme"), job("p1", "o"), job("p2", None))) == []
    assert merge_candidates(batch(org("o", "Acme"), job("p1", None), job("p2", "o"))) == []


def test_a_name_at_exactly_the_threshold_is_a_candidate() -> None:
    assert merge_candidates(batch(org("1", "abcdefghij"), org("2", "abcdefghik"))) == [("1", "2", 0.9)]


def test_long_names_are_scored_without_junk_heuristics() -> None:
    first = ("acababbbcbaababbcacbbcacabaaaccabcabcacabbcabacabbabccaaccbacbcccbccabbcbcbcabacbbcabccccbabccaacbbbc"
             "ababccccbcaacaaaccabcbcbbbccccabccaccababbccacbbbbbaccccbbcaacaccaacbacaaabababacabbaaabcacbccbbcbbbaab"
             "bbababccacbaaab")
    second = "".join("d" if i % 25 == 0 else c for i, c in enumerate(first))  # ten edits in 220 characters
    assert [c[:2] for c in merge_candidates(batch(org("1", first), org("2", second)))] == [("1", "2")]


def test_positions_at_variant_spellings_of_one_employer_carry_the_org_score() -> None:
    result = merge_candidates(batch(org("o1", "Initech Systems"), org("o2", "Initech Systemz"),
                                    job("p1", "o1"), job("p2", "o2")))
    assert [(a, b) for a, b, _ in result] == [("o1", "o2"), ("p1", "p2")]
    assert result[0][2] == result[1][2] < 1.0


def test_best_score_first_then_smaller_ids() -> None:
    result = merge_candidates(batch(
        org("a0", "Initech Systems"), org("a0b", "Initech Systemz"),  # 0.93
        org("o", "Acme"), job("a1", "o"), job("a4", "o"),
        org("q", "Globex"), job("a2", "q", "Cook"), job("a3", "q", "Cook"),
    ))
    assert [(a, b) for a, b, _ in result] == [("a1", "a4"), ("a2", "a3"), ("a0", "a0b")]
    assert [s for *_, s in result][:2] == [1.0, 1.0] and result[2][2] < 1.0
