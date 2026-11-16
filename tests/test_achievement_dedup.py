"""Achievement duplicates: the same accomplishment worded differently by two sources under one position."""

import random

from hypothesis import given, strategies as st

from career_buddy.domain.dedup import merge_candidates
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind

API = "Cut API p95 latency by 40% by caching responses in Redis"
PARAPHRASE = "Reduced p95 API latency 40% through Redis response caching"
OTHER_RESULT = "Cut API p95 latency by 60% by caching responses in Redis"
UNRELATED = "Led migration of billing service to Kubernetes"


def batch(*pairs: tuple[str, str, str]) -> FactBatch:
    """(id, title, parent position id) for each achievement."""
    facts = tuple(Fact(i, FactKind.ACHIEVEMENT, title, {}, "s") for i, title, _ in pairs)
    links = tuple(Link(parent, i, LinkKind.ACHIEVED) for i, _, parent in pairs)
    return FactBatch(facts, links)


def pairs(found: list[tuple[str, str, float]]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b, _ in found}


def test_a_paraphrase_under_the_same_position_is_a_candidate() -> None:
    found = merge_candidates(batch(("a", API, "p1"), ("b", PARAPHRASE, "p1")))
    assert pairs(found) == {frozenset(("a", "b"))}


def test_the_same_result_with_different_numbers_is_not_a_candidate() -> None:
    assert merge_candidates(batch(("a", API, "p1"), ("b", OTHER_RESULT, "p1"))) == []


def test_unrelated_achievements_are_not_candidates() -> None:
    assert merge_candidates(batch(("a", API, "p1"), ("b", UNRELATED, "p1"))) == []


def test_the_same_paraphrase_under_different_positions_is_not_a_candidate() -> None:
    assert merge_candidates(batch(("a", API, "p1"), ("b", PARAPHRASE, "p2"))) == []


def test_the_tools_a_source_names_count_toward_the_match() -> None:
    other = Fact("b", FactKind.ACHIEVEMENT, "Reduced p95 latency 40% with Redis caching", {}, "s")
    bare = Fact("a", FactKind.ACHIEVEMENT, "Cut p95 latency 40%", {}, "s")
    detailed = Fact("a", FactKind.ACHIEVEMENT, "Cut p95 latency 40%", {"tools": "Redis caching"}, "s")
    links = (Link("p1", "a", LinkKind.ACHIEVED), Link("p1", "b", LinkKind.ACHIEVED))
    assert merge_candidates(FactBatch((bare, other), links)) == []
    assert pairs(merge_candidates(FactBatch((detailed, other), links))) == {frozenset(("a", "b"))}


titles = st.sampled_from([API, PARAPHRASE, OTHER_RESULT, UNRELATED, "Led a team of 5 engineers", "Shipped the mobile app"])
rows = st.lists(st.tuples(st.sampled_from("abcdef"), titles, st.sampled_from(["p1", "p2"])), max_size=6,
                unique_by=lambda row: row[0])


@given(rows, st.randoms(use_true_random=False))
def test_achievement_candidates_are_order_independent_and_never_self_pairs(rows, rnd: random.Random) -> None:
    shuffled = list(rows)
    rnd.shuffle(shuffled)
    forward = merge_candidates(batch(*rows))
    backward = merge_candidates(batch(*shuffled))
    assert all(a != b and a < b for a, b, _ in forward)
    assert sorted(forward) == sorted(backward)
