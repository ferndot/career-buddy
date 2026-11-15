"""manual_fact: the exact batch for every kind, and the exact refusals."""

import pytest

from career_graph.domain.manual import manual_fact
from career_graph.domain.model import Fact, FactBatch, FactKind, InvalidFact, Link, LinkKind, fact_id

PERSON = Fact("person-1", FactKind.PERSON, "Ada")
JOB = Fact("job-1", FactKind.POSITION, "Engineer")


def org(name: str) -> Fact:
    return Fact(fact_id(FactKind.ORGANIZATION, name), FactKind.ORGANIZATION, name, {}, "manual")


def test_a_position_with_an_organization_adds_both_and_links_them() -> None:
    batch = manual_fact(FactKind.POSITION, "  Engineer ", PERSON, {"organization": " Acme ", "period": " 2020 ", "x": " "})
    position = Fact(fact_id(FactKind.POSITION, "Engineer", "Acme"), FactKind.POSITION, "Engineer",
                    {"period": "2020"}, "manual")
    assert batch == FactBatch(
        (position, org("Acme")),
        (Link("person-1", position.id, LinkKind.HAS_POSITION), Link(position.id, org("Acme").id, LinkKind.AT)),
    )


def test_a_position_without_an_organization_is_alone() -> None:
    position = Fact(fact_id(FactKind.POSITION, "Engineer", ""), FactKind.POSITION, "Engineer", {}, "manual")
    batch = manual_fact(FactKind.POSITION, "Engineer", PERSON, {})
    assert batch == FactBatch((position,), (Link("person-1", position.id, LinkKind.HAS_POSITION),))


def test_an_education_keeps_its_school_and_attends_the_organization() -> None:
    edu = Fact(fact_id(FactKind.EDUCATION, "BSc", "MIT"), FactKind.EDUCATION, "BSc", {"school": "MIT"}, "manual")
    batch = manual_fact(FactKind.EDUCATION, "BSc", PERSON, {"school": "MIT"})
    assert batch == FactBatch(
        (edu, org("MIT")),
        (Link("person-1", edu.id, LinkKind.HAS_EDUCATION), Link(edu.id, org("MIT").id, LinkKind.ATTENDED)),
    )


def test_an_education_without_a_school_is_alone() -> None:
    edu = Fact(fact_id(FactKind.EDUCATION, "BSc", ""), FactKind.EDUCATION, "BSc", {}, "manual")
    assert manual_fact(FactKind.EDUCATION, "BSc", PERSON, {}) == FactBatch(
        (edu,), (Link("person-1", edu.id, LinkKind.HAS_EDUCATION),))


def test_an_achievement_is_scoped_to_its_position() -> None:
    ach = Fact(fact_id(FactKind.ACHIEVEMENT, "Shipped", "job-1"), FactKind.ACHIEVEMENT, "Shipped", {}, "manual")
    assert manual_fact(FactKind.ACHIEVEMENT, "Shipped", JOB, {}) == FactBatch(
        (ach,), (Link("job-1", ach.id, LinkKind.ACHIEVED),))


def test_a_skill_is_not_scoped_to_its_person() -> None:
    skill = Fact(fact_id(FactKind.SKILL, "Go", ""), FactKind.SKILL, "Go", {}, "manual")
    assert manual_fact(FactKind.SKILL, "Go", PERSON, {}) == FactBatch(
        (skill,), (Link("person-1", skill.id, LinkKind.HAS_SKILL),))


def test_a_fact_without_a_parent_is_refused_by_kind() -> None:
    with pytest.raises(InvalidFact) as error:
        manual_fact(FactKind.SKILL, "Go", None, {})
    assert str(error.value) == "A Skill needs a parent"


@pytest.mark.parametrize("title, parent", [("", PERSON), ("  ", PERSON), ("Go", JOB)])
def test_a_blank_title_or_wrong_parent_is_refused(title: str, parent: Fact) -> None:
    with pytest.raises(InvalidFact) as error:
        manual_fact(FactKind.SKILL, title, parent, {})
    assert str(error.value) == "A title and a valid parent are required"
