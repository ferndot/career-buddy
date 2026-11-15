"""Shared sample data for the document tests."""

from career_graph.domain.document import Document
from career_graph.domain.profile import EducationView, PositionView, Profile
from career_graph.domain.templates import build_document, get_template

PROFILE = Profile(
    name="Jane Doe",
    attributes={"headline": "Platform engineer", "summary": "Builds data pipelines", "location": "Lisbon, Portugal"},
    positions=(
        PositionView("Senior Engineer", "Acme Corp", {"started": "Mar 2019", "finished": "Jan 2023"},
                     ("Cut build times by 60%",)),
        PositionView("Engineer", "Globex", {"started": "Jun 2023"}, ()),
        PositionView("Analyst", "Analytical Society", {"period": "2010 - 2015"}, ("Wrote an algorithm",)),
    ),
    education=(EducationView("University of Lisbon", "BSc Computer Science"),),
    skills=("Python", "Kubernetes"),
)


def sample_document() -> Document:
    return build_document(PROFILE, get_template("resume-classic"))
