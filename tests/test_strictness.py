"""Strictness loosens wording only: specifics are rejected at every level; a longer paraphrase passes at Balanced and Loose, not at Strict."""

import pytest
from hypothesis import given, strategies as st

from career_buddy.domain.generation import Brief, BriefFact, Claim
from career_buddy.domain.grounding import ground, verify_prose
from career_buddy.domain.rewording import verify_rewording
from career_buddy.domain.strictness import LEVELS

SOURCE = "Cut build times by 60% for Acme Corp using Kubernetes"
FACTS = (BriefFact("a1", "achievement", "Cut build times by 60% using Kubernetes", "p1"), BriefFact("p1", "position", "Senior Engineer at Acme Corp"))
STRETCH = "Led the effort that cut build times by 60% using Kubernetes"  # 1.5x the fact: wording only
STRETCHED = "Led the effort that cut build times by 60% across the whole engineering team using Kubernetes"  # 2.3x


def bullet(text: str, level: str) -> list[str]:
    brief = Brief("resume", FACTS, strictness=level)  # type: ignore[arg-type]
    kept, rejected = ground(brief, {"bullet:a1": Claim(text, ("a1",))})
    return [r for rej in rejected for r in rej.reasons]


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("text", ["Cut build times by 75% using Kubernetes", "Cut build times by 60% using Terraform", "Cut build times by 60% at Globex using Kubernetes",
                                  "Cut build times by 60% using Kubernetes and a PMP"])
def test_a_new_number_name_or_tool_is_rejected_at_every_level(level: str, text: str) -> None:
    assert bullet(text, level)


def test_a_longer_paraphrase_passes_balanced_and_loose_but_not_strict() -> None:
    assert bullet(STRETCH, "strict") and not bullet(STRETCH, "balanced") and not bullet(STRETCH, "loose")
    assert bullet(STRETCHED, "balanced") and not bullet(STRETCHED, "loose")


def test_prose_wording_loosens_with_the_level_and_its_specifics_never_do() -> None:
    long_prose = "I " + "build reliable platforms and ship them well. " * 14  # past the strict allowance
    assert verify_prose(SOURCE, long_prose, strictness="strict") and not verify_prose(SOURCE, long_prose, strictness="loose")
    for level in LEVELS:
        assert verify_prose(SOURCE, "I cut it by 75% at Globex.", strictness=level)


def test_the_default_for_rewording_is_strict() -> None:
    assert verify_rewording("aaaaaaaaaa", "aaaaaaaaaaaaaa", ()) == verify_rewording("aaaaaaaaaa", "aaaaaaaaaaaaaa", (), strictness="strict") != []


words = st.text("abcdefghij", min_size=1, max_size=6)


@given(st.lists(words, min_size=1, max_size=10), st.integers(0, 99999), st.sampled_from(LEVELS))
def test_a_number_the_source_lacks_is_rejected_at_every_level(source_words: list[str], number: int, level: str) -> None:
    source = " ".join(source_words)
    assert any(r.startswith("number") for r in verify_rewording(source, f"{source} {number + 100000}", (), strictness=level))
    assert any(r.startswith("number") for r in verify_prose(source, f"{source} {number + 100000}", strictness=level))


@given(st.lists(words, min_size=1, max_size=10), st.lists(words, max_size=10))
def test_a_looser_level_never_rejects_what_a_stricter_one_accepts(source_words: list[str], extra: list[str]) -> None:
    source, candidate = " ".join(source_words), " ".join(source_words + extra)
    results = [bool(verify_rewording(source, candidate, (), strictness=level)) for level in LEVELS]
    assert results == sorted(results, reverse=True)
