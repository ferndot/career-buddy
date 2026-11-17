"""Tailoring: job terms, scoring, ordering, and the report. All pure."""

from hypothesis import given, strategies as st

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.profile import EducationView, PositionView, Profile
from career_buddy.domain.tailoring import apply_overrides, job_terms, tailor
from career_buddy.domain.templates import build_document, get_template

CLASSIC, COMPACT = get_template("resume-classic"), get_template("resume-compact")  # for the document builder only


def position(title: str, bullets: list[str], dates: dict[str, str] = {"started": "2020", "finished": "2021"}, skills: tuple[str, ...] = (), pid: str = "p") -> PositionView:
    return PositionView(title, "Org", dates, tuple(bullets), skills, pid,
                        tuple(f"{pid}-{i}" for i in range(len(bullets))))


def weights(job: str) -> dict[str, float]:
    return {t.label: t.weight for t in job_terms(job)}


def test_job_terms_drop_stopwords_and_add_bigrams() -> None:
    labels = weights("We are looking for build speed experts").keys()
    assert {"build", "speed", "build speed", "experts"} <= labels
    assert not labels & {"we", "are", "for", "looking for"}


def test_weight_rises_for_frequent_capitalized_tech_and_requirements_terms() -> None:
    w = weights("We value teamwork. We value teamwork and docs. Our Kubernetes stack uses C++ daily.\n"
                "Requirements:\n- plumbing")
    assert w["teamwork"] > w["docs"]  # frequent
    assert w["c++"] > w["daily"]  # tech-shaped
    assert w["kubernetes"] > w["stack"]  # capitalized
    assert w["plumbing"] > w["stack"]  # in a requirements section


def test_bullets_reorder_toward_the_job_and_ties_keep_original_order() -> None:
    profile = Profile(positions=(position("Dev", ["Wrote docs", "Ran Kubernetes clusters", "Fixed bugs"]),))
    tailored, _ = tailor(profile, "We need Kubernetes experience")
    assert tailored.positions[0].achievements == ("Ran Kubernetes clusters", "Wrote docs", "Fixed bugs")
    assert tailored.positions[0].achievement_ids == ("p-1", "p-0", "p-2")


def test_every_bullet_is_kept() -> None:
    bullets = [f"Did task {n}" for n in range(8)]
    profile = Profile(positions=(position("Dev", bullets),))
    assert tailor(profile, "")[0].positions[0].achievements == tuple(bullets)


def test_positions_are_all_kept_in_reverse_chronological_order() -> None:
    profile = Profile(positions=(
        PositionView("Old", "A", {"started": "Jan 2010", "finished": "Dec 2012"}, id="1"),
        PositionView("Now", "B", {"started": "Jun 2023"}, id="2"),
        PositionView("Mid", "C", {"started": "2015", "finished": "2019"}, id="3"),
        PositionView("Mid2", "D", {"started": "2015", "finished": "2019"}, id="4"),
    ))
    tailored, _ = tailor(profile, "Old Mid Now")
    assert [p.title for p in tailored.positions] == ["Now", "Mid", "Mid2", "Old"]


def test_skills_matched_first_in_job_order_then_by_position_use() -> None:
    skills = tuple(f"S{n}" for n in range(20)) + ("Python", "Go", "Kubernetes")
    profile = Profile(skills=skills, skill_ids=tuple(f"id-{s}" for s in skills),
                      positions=(position("Dev", [], skills=("Go",)), position("Dev2", [], skills=("S5", "Go"), pid="q")))
    tailored, _ = tailor(profile, "We use Kubernetes and Python daily")
    assert tailored.skills[:2] == ("Kubernetes", "Python")
    assert tailored.skills[2:4] == ("Go", "S5")  # then by how many positions use them
    assert len(tailored.skills) == len(skills)
    assert tailored.skill_ids[0] == "id-Kubernetes"


def test_summary_is_the_stored_summary_or_nothing() -> None:
    profile = Profile(name="J", attributes={"summary": "Original words"}, id="u")
    tailored, _ = tailor(profile, "Kubernetes")
    assert tailored.attributes["summary"] == "Original words"
    assert "Summary" not in build_document(Profile(name="J", id="u"), CLASSIC).headings()


def test_report_lists_matched_and_missing_terms_and_adds_nothing() -> None:
    profile = Profile(positions=(position("Dev", ["Ran Kubernetes clusters"]),), skills=("Python",))
    tailored, report = tailor(profile, "Requirements:\n- Kubernetes\n- Terraform")
    assert "kubernetes" in report.matched and "terraform" not in report.matched
    assert "terraform" in report.missing and "kubernetes" not in report.missing
    assert "Terraform" not in " ".join(build_document(tailored, CLASSIC).lines())


def test_overrides_replace_bullet_text_as_user_lines_and_leave_headings_alone() -> None:
    doc = Document(Line("J"), sections=(Section("Experience", (
        Entry(Line("Dev, Org", "p"), bullets=(Line("old", "p-0"),)),)),))
    out = apply_overrides(doc, {"p-0": "new", "p": "hacked"})
    entry = out.sections[0].entries[0]
    assert entry.bullets[0] == Line("new", "p-0", Origin.USER) and entry.heading.text == "Dev, Org"


words = st.sampled_from(["Kubernetes", "python", "build", "AWS", "team", "speed", "C++", "docs", "lead"])
sentence = st.lists(words, min_size=1, max_size=5).map(" ".join)


@st.composite
def profiles(draw) -> Profile:
    n = draw(st.integers(0, 4))
    positions = tuple(
        position(draw(sentence), draw(st.lists(sentence, max_size=7)), draw(st.sampled_from([{"started": "2010", "finished": "2012"}, {"started": "2019", "finished": "2023"}, {}])),
                 tuple(draw(st.lists(words, max_size=3))), pid=f"p{i}")
        for i in range(n)
    )
    return Profile(name="J", attributes={"summary": draw(sentence)}, positions=positions,
                   skills=tuple(draw(st.lists(words, max_size=20, unique=True))), id="u")


@given(profiles(), st.text(max_size=80) | st.lists(words, max_size=8).map(" ".join), st.sampled_from([CLASSIC, COMPACT]))
def test_tailoring_never_adds_or_drops_a_fact_and_never_adds_a_line_without_a_source(profile: Profile, job: str, spec) -> None:
    tailored, _ = tailor(profile, job)
    doc = build_document(tailored, spec)
    for section in doc.sections:
        for entry in section.entries:
            for line in entry.lines():
                assert line.source_fact_id or line.origin in (Origin.USER, Origin.BOILERPLATE)
    original = {a for p in profile.positions for a in p.achievements}
    assert all(a in original for p in tailored.positions for a in p.achievements)
    assert {p.id for p in tailored.positions} == {p.id for p in profile.positions}
    assert sorted(a for p in tailored.positions for a in p.achievement_ids) == sorted(a for p in profile.positions for a in p.achievement_ids)
    assert sorted(tailored.skills) == sorted(profile.skills) and tailored.education == profile.education


SKILLS = Profile(skills=("Go", "Python", "Rust", "Zig"), skill_ids=("s1", "s2", "s3", "s4"),
                 education=(EducationView("MIT", "BSc", id="e1"), EducationView("ETH", "MSc", id="e2")))


def test_skills_and_education_are_all_kept_with_the_job_matches_first() -> None:
    tailored, _ = tailor(SKILLS, "We use Zig and Rust")
    assert tailored.skills == ("Zig", "Rust", "Go", "Python")  # matched in the order the posting names them, then the rest
    assert set(tailored.skill_ids) == {"s1", "s2", "s3", "s4"} and tailored.education == SKILLS.education


@given(st.text(max_size=30))
def test_a_job_text_only_reorders_the_skills(job) -> None:
    assert sorted(tailor(SKILLS, job)[0].skill_ids) == ["s1", "s2", "s3", "s4"]
