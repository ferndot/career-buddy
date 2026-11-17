"""Company-grouped resumes whose bullets and separators extract as U+FFFD, through the offline extractor."""

import asyncio

from career_buddy.adapters.inference.heuristic import HeuristicExtractor
from career_buddy.adapters.readers.pdf_text import PdfTextReader
from career_buddy.domain.model import FactBatch
from layouts import pdf
from resume_fixtures import FFFD, resume_html, resume_text


def extract(text: str) -> FactBatch:
    return asyncio.run(HeuristicExtractor().extract(text, "t"))


def of(batch: FactBatch, kind: str) -> list:
    return [f for f in batch.facts if f.kind == kind]


def assert_grouped_resume_facts(batch: FactBatch) -> None:
    (person,) = of(batch, "Person")
    assert person.title == "Mira Valdane"
    assert person.attributes == {"email": "mira.valdane@example.com", "phone": "(206) 555-0142"}

    org, other = "Northwind Labs / Contoso Works", "Fabrikam Systems"
    positions = {f.title: f.attributes for f in of(batch, "Position")}
    assert positions == {
        "Principal Software Engineer / Product Engineer": {"started": "2019-03", "finished": "present"},
        "Staff Engineer": {"started": "2019-03", "finished": "present"},
        "Software Engineer": {"started": "2014-06", "finished": "2019-02"},
    }
    assert {f.title for f in of(batch, "Organization")} >= {org, other}
    assert [f.title for f in of(batch, "Achievement")] == [
        "Led the platform rewrite", "Cut deploy time by 60%", "Mentored five engineers", "Built the billing pipeline",
    ]

    assert [(f.title, f.attributes) for f in of(batch, "Education")] == [
        ("BSc Computer Science", {"school": "Lakeside University", "started": "2014", "finished": "2017"}),
        ("MSc Data Engineering", {"school": "Harbor College", "started": "2017", "finished": "2019"}),
    ]
    assert [f.title for f in of(batch, "Skill")] == [
        "Python", "Go", "SQL", "AWS", "Postgres", "Kafka", "Distributed systems", "API design", "FastAPI", "Pydantic",
    ]


def test_grouped_resume_with_replacement_character_separators() -> None:
    assert_grouped_resume_facts(extract(resume_text()))


def test_bullets_attach_to_the_most_recent_title() -> None:
    batch = extract(resume_text())
    by_id = {f.id: f.title for f in batch.facts}
    achieved: dict[str, list[str]] = {}
    for link in batch.links:
        if link.kind == "ACHIEVED":
            achieved.setdefault(by_id[link.source_id], []).append(by_id[link.target_id])
    assert achieved == {
        "Principal Software Engineer / Product Engineer": ["Led the platform rewrite", "Cut deploy time by 60%"],
        "Staff Engineer": ["Mentored five engineers"],
        "Software Engineer": ["Built the billing pipeline"],
    }


def test_a_phone_that_lost_its_opening_parenthesis_is_reported_as_written() -> None:
    (person,) = of(extract(resume_text("206) 555-0142")), "Person")
    assert person.attributes["phone"] == "206) 555-0142"


def test_category_labels_are_not_skills() -> None:
    skills = {f.title for f in of(extract(resume_text()), "Skill")}
    assert not skills & {"Languages", "Cloud", "Data & Tools", "Cloud, Data & Tools", "Concepts", "AI & Machine Learning",
                         "AI & Machine Learning:", "Frameworks & Libraries", "Data & Tools"}


def test_a_replacement_character_starts_a_bullet_and_is_never_left_in_a_fact() -> None:
    batch = extract(resume_text())
    assert not [f for f in batch.facts if FFFD in f.title or any(FFFD in v for v in f.attributes.values())]


def test_grouped_resume_through_the_pdf_reader(chromium) -> None:
    extracted = PdfTextReader().read(pdf(resume_html()))
    assert_grouped_resume_facts(extract(extracted.text))
