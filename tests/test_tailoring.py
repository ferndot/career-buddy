"""Tailoring: job terms, scoring, selection under template caps, and the report. All pure."""

from hypothesis import given, strategies as st

from career_graph.domain.document import Document, Entry, Line, Origin, Section
from career_graph.domain.profile import PositionView, Profile
from career_graph.domain.tailoring import apply_overrides, job_terms, tailor
from career_graph.domain.templates import build_document, get_template

CLASSIC, COMPACT = get_template("resume-classic"), get_template("resume-compact")


def position(title: str, bullets: list[str], period: str = "2020 - 2021", skills: tuple[str, ...] = (), pid: str = "p") -> PositionView:
    return PositionView(title, "Org", {"period": period}, tuple(bullets), skills, pid,
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
    tailored, _ = tailor(profile, "We need Kubernetes experience", CLASSIC)
    assert tailored.positions[0].achievements == ("Ran Kubernetes clusters", "Wrote docs", "Fixed bugs")
    assert tailored.positions[0].achievement_ids == ("p-1", "p-0", "p-2")


def test_template_caps_bullets_per_position_and_keeps_at_least_one() -> None:
    bullets = [f"Did task {n}" for n in range(8)]
    profile = Profile(positions=(position("Dev", bullets),))
    assert len(tailor(profile, "", CLASSIC)[0].positions[0].achievements) == 5
    assert len(tailor(profile, "", COMPACT)[0].positions[0].achievements) == 3
    assert tailor(profile, "", COMPACT)[0].positions[0].achievements == ("Did task 0", "Did task 1", "Did task 2")
    assert len(tailor(Profile(positions=(position("Dev", ["Only"]),)), "", COMPACT)[0].positions[0].achievements) == 1


def test_positions_are_all_kept_in_reverse_chronological_order() -> None:
    profile = Profile(positions=(
        PositionView("Old", "A", {"started": "Jan 2010", "finished": "Dec 2012"}, id="1"),
        PositionView("Now", "B", {"started": "Jun 2023"}, id="2"),
        PositionView("Mid", "C", {"period": "2015 - 2019"}, id="3"),
        PositionView("Mid2", "D", {"period": "2015 - 2019"}, id="4"),
    ))
    tailored, _ = tailor(profile, "Old Mid Now", COMPACT)
    assert [p.title for p in tailored.positions] == ["Now", "Mid", "Mid2", "Old"]


def test_skills_matched_first_in_job_order_then_by_position_use_and_capped() -> None:
    skills = tuple(f"S{n}" for n in range(20)) + ("Python", "Go", "Kubernetes")
    profile = Profile(skills=skills, skill_ids=tuple(f"id-{s}" for s in skills),
                      positions=(position("Dev", [], skills=("Go",)), position("Dev2", [], skills=("S5", "Go"), pid="q")))
    tailored, _ = tailor(profile, "We use Kubernetes and Python daily", CLASSIC)
    assert tailored.skills[:2] == ("Kubernetes", "Python")
    assert tailored.skills[2:4] == ("Go", "S5")  # then by how many positions use them
    assert len(tailored.skills) == 15 and len(tailor(profile, "", COMPACT)[0].skills) == 10
    assert tailored.skill_ids[0] == "id-Kubernetes"


def test_summary_is_the_stored_summary_or_nothing() -> None:
    profile = Profile(name="J", attributes={"summary": "Original words"}, id="u")
    tailored, _ = tailor(profile, "Kubernetes", CLASSIC)
    assert tailored.attributes["summary"] == "Original words"
    assert "Summary" not in build_document(Profile(name="J", id="u"), CLASSIC).headings()


def test_report_lists_matched_and_missing_terms_and_adds_nothing() -> None:
    profile = Profile(positions=(position("Dev", ["Ran Kubernetes clusters"]),), skills=("Python",))
    tailored, report = tailor(profile, "Requirements:\n- Kubernetes\n- Terraform", CLASSIC)
    assert "kubernetes" in report.matched and "terraform" not in report.matched
    assert "terraform" in report.missing and "kubernetes" not in report.missing
    assert "Terraform" not in " ".join(build_document(tailored, CLASSIC).lines())


def test_selection_keeps_only_the_checked_bullets_in_score_order() -> None:
    profile = Profile(positions=(position("Dev", ["a one", "b two", "c Kubernetes"]),))
    tailored, _ = tailor(profile, "Kubernetes", CLASSIC, selection=frozenset({"p-0", "p-2"}))
    assert tailored.positions[0].achievement_ids == ("p-2", "p-0")


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
        position(draw(sentence), draw(st.lists(sentence, max_size=7)), draw(st.sampled_from(["2010 - 2012", "2019 - 2023", ""])),
                 tuple(draw(st.lists(words, max_size=3))), pid=f"p{i}")
        for i in range(n)
    )
    return Profile(name="J", attributes={"summary": draw(sentence)}, positions=positions,
                   skills=tuple(draw(st.lists(words, max_size=20, unique=True))), id="u")


@given(profiles(), st.text(max_size=80) | st.lists(words, max_size=8).map(" ".join), st.sampled_from([CLASSIC, COMPACT]))
def test_tailoring_never_adds_a_line_without_a_source_fact(profile: Profile, job: str, spec) -> None:
    tailored, _ = tailor(profile, job, spec)
    doc = build_document(tailored, spec)
    for section in doc.sections:
        for entry in section.entries:
            for line in entry.lines():
                assert line.source_fact_id or line.origin in (Origin.USER, Origin.BOILERPLATE)
    original = {a for p in profile.positions for a in p.achievements}
    assert all(a in original for p in tailored.positions for a in p.achievements)
    assert {p.id for p in tailored.positions} == {p.id for p in profile.positions}
    assert set(tailored.skills) <= set(profile.skills)
