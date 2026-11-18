"""The fit check: posting terms in the text, in the summary and in the first bullets; coverage issues count against it. Pure."""

from hypothesis import given, strategies as st

from career_buddy.domain.coverage import Issue
from career_buddy.domain.fit import PASS, fit
from career_buddy.domain.generation import Brief

BRIEF = Brief("resume", (), terms=("Kubernetes", "Python", "CI/CD"))
GOOD = {"summary": "Engineer who runs Kubernetes and Python platforms.", "bullet:a1": "Cut build times on Kubernetes", "bullet:a2": "Wrote Python tools"}


def test_a_draft_that_leads_with_the_posting_terms_passes() -> None:
    score, issue = fit(BRIEF, GOOD)
    assert score >= PASS and issue is None


def test_a_summary_and_first_bullets_without_a_term_are_named_with_the_slots_to_rewrite() -> None:
    score, issue = fit(BRIEF, {"summary": "A hard worker.", "bullet:a1": "Cut build times", "bullet:a2": "Fixed things", "bullet:a3": "Used tools"})
    assert score < PASS and issue and issue.code == "weak_fit"
    assert issue.slots == ("summary", "bullet:a1") and "summary names none" in issue.text and "lacks: Kubernetes, Python, CI/CD" in issue.text


def test_a_coverage_issue_lowers_the_score() -> None:
    flag = Issue("missing_position", "x")
    assert fit(BRIEF, GOOD, [flag])[0] < fit(BRIEF, GOOD)[0]


def test_no_terms_means_nothing_to_judge() -> None:
    assert fit(Brief("resume", ()), {"summary": "x"}) == (1.0, None)


@given(st.dictionaries(st.sampled_from(["summary", "bullet:a1", "para:1"]), st.text(max_size=40)), st.integers(0, 3))
def test_the_score_is_between_zero_and_one(kept: dict[str, str], flags: int) -> None:
    score, issue = fit(BRIEF, kept, [Issue("thin_position", "x")] * flags)
    assert 0.0 <= score <= 1.0 and (issue is None) == (score >= PASS)
