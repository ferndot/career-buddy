"""Template specs and the resume document, pinned exactly."""

from career_buddy.domain.document import Entry, Line
from career_buddy.domain.profile import EducationView, PositionView, Profile
from career_buddy.domain.templates import build_document, get_template


def test_every_letter_template_is_a_job_board_letter_with_the_same_styles() -> None:
    letters = [get_template(i) for i in ("cover-letter", "cover-letter-modern")]
    assert all((t.kind, t.sections, t.required, t.optional) == ("letter", (), (), ("recipient",)) for t in letters)
    assert letters[0].styles == letters[1].styles and len(letters[0].styles) >= 3
    assert letters[0].layout != letters[1].layout


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
