"""BatchBuilder: the exact facts and links each call produces."""

from career_buddy.domain.builder import BatchBuilder
from career_buddy.domain.document import Document, Entry, Line, Section
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind, fact_id

K, L = FactKind, LinkKind


def make(kind: FactKind, title: str, scope: str = "", **attrs: str) -> Fact:
    return Fact(fact_id(kind, title, scope), kind, title, attrs, "src")


def test_a_position_with_achievements_and_skills() -> None:
    builder = BatchBuilder("src")
    person = builder.person("Ada", location=" Rome ", empty="  ")
    builder.position(person, "Eng", "Acme", achievements=("Did it",), skills=("Go", "Rust"), period=" 2020 ", gap="")
    ada = make(K.PERSON, "Ada", location="Rome")
    org, pos = make(K.ORGANIZATION, "Acme"), make(K.POSITION, "Eng", "Acme", period="2020")
    ach = make(K.ACHIEVEMENT, "Did it", "Eng|Acme")
    go, rust = make(K.SKILL, "Go"), make(K.SKILL, "Rust")
    assert builder.build() == FactBatch(
        (ada, org, pos, ach, go, rust),
        (Link(ada.id, pos.id, L.HAS_POSITION), Link(pos.id, org.id, L.AT), Link(pos.id, ach.id, L.ACHIEVED),
         Link(ada.id, go.id, L.HAS_SKILL), Link(pos.id, go.id, L.USES_SKILL),
         Link(ada.id, rust.id, L.HAS_SKILL), Link(pos.id, rust.id, L.USES_SKILL)),
    )


def test_a_loose_skill_is_linked_to_the_person_only() -> None:
    builder = BatchBuilder("src")
    person = builder.person("Ada")
    builder.skill(person, "Go")
    assert builder.build().links == (Link(person, make(K.SKILL, "Go").id, L.HAS_SKILL),)


def test_education_remembers_its_school() -> None:
    builder = BatchBuilder("src")
    person = builder.person("Ada")
    builder.education(person, "MIT", "BSc", year="1999")
    edu = make(K.EDUCATION, "BSc", "MIT", school="MIT", year="1999")
    school = make(K.ORGANIZATION, "MIT")
    assert builder.build().facts[1:] == (edu, school)
    assert builder.build().links == (Link(person, edu.id, L.HAS_EDUCATION), Link(edu.id, school.id, L.ATTENDED))


def test_the_same_claim_twice_is_one_fact_and_one_link() -> None:
    builder = BatchBuilder("src")
    person = builder.person("Ada")
    builder.skill(person, "Go")
    builder.skill(person, "Go")
    assert len(builder.build().facts) == 2 and len(builder.build().links) == 1


def test_document_lines_skip_an_untitled_section_heading() -> None:
    doc = Document(Line("Ada"), (), (Section("", (Entry(paragraph=Line("Dear you")),)),))
    assert doc.lines() == ["Ada", "Dear you"]
