"""What is known about an achievement: its title, details, and the wording of every source that stated it."""

from career_graph.domain.knowledge import details, knowledge
from career_graph.domain.model import Fact, FactKind


def achievement(id: str, title: str, **attrs: str) -> Fact:
    return Fact(id, FactKind.ACHIEVEMENT, title, dict(attrs), "source")


def test_a_fact_with_no_details_is_only_its_title() -> None:
    assert knowledge(achievement("a", "Migrated 40 services to Kubernetes")) == "Migrated 40 services to Kubernetes"


def test_details_are_listed_under_their_names() -> None:
    fact = achievement("a", "Cut build times", result="60%", tools="Bazel, CI")
    assert knowledge(fact) == "Cut build times\nResult: 60%\nTools: Bazel, CI"


def test_absorbed_facts_add_their_wording_and_details_without_repeating_them() -> None:
    main = achievement("a", "Cut build times", result="60%")
    other = achievement("b", "Reduced CI build time", result="60%", tools="Bazel")
    assert knowledge(main, [other]) == (
        "Cut build times\nOther wordings: Reduced CI build time\nResult: 60%\nTools: Bazel"
    )


def test_values_that_differ_only_in_case_or_spacing_count_once() -> None:
    main = achievement("a", "Cut build times", tools="Bazel  CI")
    other = achievement("b", "cut build times", tools="bazel ci")
    assert knowledge(main, [other]) == "Cut build times\nTools: Bazel CI"


def test_details_leave_out_the_position_and_employer() -> None:
    fact = achievement("a", "Cut build times", result="60%", period="2019 - 2021")
    assert details(fact) == "Cut build times 60%"
