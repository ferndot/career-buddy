"""The Document model and the resume-classic template, both pure."""

import pytest

from career_graph.domain.document import Document, Entry, Line, Origin, Section
from career_graph.domain.profile import PositionView, Profile
from career_graph.domain.templates import build_document, get_template
from samples import PROFILE

def test_document_lines_are_in_reading_order() -> None:
    doc = Document(
        name=Line("Ada"),
        intro=(Line("London"),),
        sections=(
            Section("Experience", (Entry(heading=Line("Analyst, Society"), bullets=(Line("Did a thing"),)),)),
            Section("Skills", (Entry(paragraph=Line("Math, Python")),)),
        ),
    )
    assert doc.lines() == ["Ada", "London", "Experience", "Analyst, Society", "Did a thing", "Skills", "Math, Python"]
    assert doc.headings() == ["Experience", "Skills"]


def test_resume_classic_builds_fixed_headings_in_template_order() -> None:
    doc = build_document(PROFILE, get_template("resume-classic"))
    assert doc.headings() == ["Summary", "Experience", "Education", "Skills"]
    assert doc.lines()[:3] == ["Jane Doe", "Lisbon, Portugal", "Platform engineer"]


def test_positions_put_title_organization_and_dates_on_one_line() -> None:
    lines = build_document(PROFILE, get_template("resume-classic")).lines()
    assert "Senior Engineer, Acme Corp (Mar 2019 - Jan 2023)" in lines
    assert "Engineer, Globex (Jun 2023 - Present)" in lines
    assert "Analyst, Analytical Society (2010 - 2015)" in lines
    assert lines[lines.index("Senior Engineer, Acme Corp (Mar 2019 - Jan 2023)") + 1] == "Cut build times by 60%"


def test_empty_sections_are_left_out() -> None:
    doc = build_document(Profile(name="Solo"), get_template("resume-classic"))
    assert doc.lines() == ["Solo"]


def test_unknown_template_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        get_template("resume-nope")


def test_every_line_is_a_fact_line_with_a_source() -> None:
    profile = Profile(name="Jane", positions=(PositionView("Dev", "Acme", {}, ("Shipped",), id="p1"),), id="u1")
    doc = build_document(profile, get_template("resume-classic"))
    assert doc.name.source_fact_id == "u1"
    entry = doc.sections[0].entries[0]
    assert entry.heading and entry.heading.source_fact_id == "p1" and entry.heading.origin is Origin.FACT
    assert entry.bullets[0].source_fact_id == "p1"
