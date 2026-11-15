"""assemble_profile: the exact read model for a full graph, a loose one and a person-less one."""

from career_graph.domain.model import Fact, FactBatch, FactKind, Link, LinkKind
from career_graph.domain.profile import EducationView, PositionView, Profile, assemble_profile

K = FactKind


def fact(id: str, kind: FactKind, title: str, **attrs: str) -> Fact:
    return Fact(id, kind, title, dict(attrs))


def test_a_person_with_positions_education_and_skills() -> None:
    batch = FactBatch(
        (
            fact("p", K.PERSON, "Ada", location="Rome"),
            fact("j1", K.POSITION, "Engineer", started="2020"),
            fact("o1", K.ORGANIZATION, "Acme"),
            fact("a1", K.ACHIEVEMENT, "Second", order="2"),
            fact("a2", K.ACHIEVEMENT, "First", order="1"),
            fact("s1", K.SKILL, "Go"),
            fact("j2", K.POSITION, "Cook"),
            fact("e1", K.EDUCATION, "BSc"),
            fact("o2", K.ORGANIZATION, "MIT"),
            fact("e2", K.EDUCATION, "Diploma", school="Night School"),
        ),
        (
            Link("p", "j1", LinkKind.HAS_POSITION), Link("j1", "o1", LinkKind.AT),
            Link("j1", "a1", LinkKind.ACHIEVED), Link("j1", "a2", LinkKind.ACHIEVED),
            Link("j1", "s1", LinkKind.USES_SKILL), Link("p", "s1", LinkKind.HAS_SKILL),
            Link("p", "j2", LinkKind.HAS_POSITION),
            Link("p", "e1", LinkKind.HAS_EDUCATION), Link("e1", "o2", LinkKind.ATTENDED),
            Link("p", "e2", LinkKind.HAS_EDUCATION),
        ),
    )
    assert assemble_profile(batch) == Profile(
        "Ada", {"location": "Rome"},
        (
            PositionView("Engineer", "Acme", {"started": "2020"}, ("First", "Second"), ("Go",), "j1", ("a2", "a1"), "o1"),
            PositionView("Cook", "", {}, (), (), "j2", (), ""),
        ),
        (
            EducationView("MIT", "BSc", {}, "e1", "o2"),
            EducationView("Night School", "Diploma", {"school": "Night School"}, "e2", ""),
        ),
        ("Go",), "p", ("s1",),
    )


def test_without_a_person_only_the_sorted_unique_skills_remain() -> None:
    batch = FactBatch((
        fact("s1", K.SKILL, "Rust"), fact("s2", K.SKILL, "Go"), fact("s3", K.SKILL, "Rust"),
        fact("o", K.ORGANIZATION, "Acme"), fact("s4", K.SKILL, "Hidden", hidden="true"),
    ))
    assert assemble_profile(batch) == Profile(skills=("Go", "Rust"))


def test_an_education_without_any_school_has_an_empty_school() -> None:
    batch = FactBatch((fact("p", K.PERSON, "Ada"), fact("e", K.EDUCATION, "Self-taught")),
                      (Link("p", "e", LinkKind.HAS_EDUCATION),))
    assert assemble_profile(batch).education == (EducationView("", "Self-taught", {}, "e", ""),)
