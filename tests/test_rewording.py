"""verify_rewording: the gate every LLM candidate passes before the user sees it. Pure."""

import pytest

from career_buddy.domain.rewording import verify_rewording

SOURCE = "Cut build times by 60% across 12 services"


def verify(candidate: str, source: str = SOURCE, **kw) -> list[str]:
    return verify_rewording(source, candidate, kw.pop("skills", ("Python",)), **kw)


def test_a_candidate_that_keeps_the_facts_passes() -> None:
    assert verify("Reduced build times by 60% across 12 services") == []


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        ("Cut build times by 75% across 12 services", "number"),
        ("Cut build times by 60% across 12 services at Google", "new term"),
        ("Cut build times by 60% across 12 services using Terraform", "new term"),
        ("Cut build times by 60% across 12 services — fast", "banned marker"),
        ("Cut build times by 60% across 12 services, a huge reduction in total", "too long"),
    ],
)
def test_candidates_are_rejected_with_a_reason(candidate: str, reason: str) -> None:
    assert any(reason in r for r in verify(candidate))


def test_a_flagged_ambiguous_word_does_not_reject_the_candidate() -> None:
    assert verify("Cut potential build times by 60% across 12 services") == []


def test_a_profile_skill_or_a_source_term_is_not_new() -> None:
    assert verify("Cut build times by 60% across 12 services with Python", skills=("Python",)) == []
    assert verify("Cut build times by 60% across 12 services with Python", skills=()) != []


def test_a_missing_term_is_never_slipped_in_even_in_lower_case() -> None:
    assert any("missing" in r for r in verify("Cut build times by 60% across 12 services via terraform", missing=("terraform",)))


def test_a_changed_title_organization_or_degree_is_rejected() -> None:
    source = "Led the Senior Engineer rotation at Acme Corp"
    assert verify("Ran the rotation at Acme Corp", source, protected=("Acme Corp",)) == []
    assert any("protected" in r for r in verify("Led the rotation at Acme", source, protected=("Acme Corp",)))
