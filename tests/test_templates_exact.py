"""Template specs and the resume document, pinned exactly."""

from career_buddy.domain.document import Entry, Line
from career_buddy.domain.profile import EducationView, PositionView, Profile
from career_buddy.domain.templates import TemplateSpec, build_document, get_template

JOB = ("company", "role")


def letter(id: str, label: str, optional=()) -> TemplateSpec:
    return TemplateSpec(id, label, (), "letter", JOB, optional)


def test_every_letter_template_has_its_exact_spec() -> None:
    assert get_template("cover-letter") == letter("cover-letter", "Cover letter", optional=("recipient",))
    assert get_template("cover-letter-email") == letter("cover-letter-email", "Cover letter (email)",
                                                         optional=("recipient",))


def build(*positions: PositionView, **attrs: str):
    profile = Profile("Ada", attrs, tuple(positions), (EducationView("MIT", "BSc", id="e1"),), ("Go",), "pid")
    return build_document(profile, get_template("resume-classic"))


def test_a_position_heading_shows_its_period_or_none() -> None:
    doc = build(
        PositionView("A", "Org", {"started": "2020", "finished": "2021"}),
        PositionView("B", "Org", {"started": "2020"}),
        PositionView("C", "Org", {"finished": "2019"}),
        PositionView("D", "", {"started": "2018", "finished": "2018"}),
        PositionView("E", ""),
    )
    headings = [e.heading.text for e in doc.sections[0].entries]
    assert headings == ["A, Org (2020 – 2021)", "B, Org (2020 – Present)", "C, Org (2019)", "D (2018)", "E"]


def test_education_lines_and_intro_lines_carry_their_sources() -> None:
    doc = build(PositionView("A", "Org"), location="Rome", headline="Analyst")
    assert doc.intro == (Line("Rome", "pid"), Line("Analyst", "pid"))
    education = next(s for s in doc.sections if s.title == "Education")
    assert education.entries == (Entry(bullets=(Line("BSc, MIT", "e1"),)),)


def test_intro_skips_missing_lines() -> None:
    assert build(location="Rome").intro == (Line("Rome", "pid"),)
    assert build(headline="Analyst").intro == (Line("Analyst", "pid"),)
