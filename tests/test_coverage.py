"""What a resume lacks that the writer cannot see: relevant roles missing or thin, and the printed length. Pure: the rules, the text the writer
is told, and how a revision merges."""

from hypothesis import given, strategies as st

from career_buddy.domain.coverage import Checked, Pages, issues, length_text, next_step, relevant_positions
from career_buddy.domain.generation import Brief, BriefFact, Caps
from career_buddy.domain.written import Bullet, Item, Section, WrittenDocument, merged, nodes

FACTS = (
    BriefFact("p1", "position", "Engineer at Acme", started="2018", finished="present"),
    BriefFact("a1", "achievement", "Cut build times", "p1"), BriefFact("a2", "achievement", "Moved services", "p1"),
    BriefFact("p2", "position", "Clerk at Old Co", started="1990", finished="Mar 1995"),
    BriefFact("b1", "achievement", "Filed paperwork", "p2"),
    BriefFact("p3", "position", "Developer at Kubes", started="1998", finished="2000"),
    BriefFact("c1", "achievement", "Ran Kubernetes clusters", "p3"),
    BriefFact("p4", "position", "Intern at Empty", finished="2024"),  # no achievement: nothing to print
)
BRIEF = Brief("resume", FACTS, terms=("Kubernetes",), sections=("experience",), caps=Caps(1, 10))
YEAR = 2026


def doc(*items: tuple[str, list[str], list[str]]) -> WrittenDocument:
    """Experience items as (position, also, achievement ids): one bullet per id."""
    return WrittenDocument(sections=(Section(key="experience", items=tuple(
        Item(position_id=p, also=tuple(also), bullets=tuple(Bullet(text=f"did {a}", fact_ids=(a,)) for a in ids)) for p, also, ids in items)),))


def codes(found) -> list[tuple[str, str]]:
    return [(i.code, i.text.split('"')[1] if '"' in i.text else "") for i in found]


def test_a_role_is_relevant_when_it_matches_a_job_term_or_ended_within_fifteen_years() -> None:
    assert relevant_positions(BRIEF, YEAR) == ["p1", "p3"]  # p1 is current, p3 matches "Kubernetes", p2 ended in 1995 and matches nothing; p4 has no achievements
    assert relevant_positions(Brief("resume", FACTS, terms=()), YEAR) == ["p1"]
    assert relevant_positions(Brief("resume", FACTS), 2010) == ["p1", "p2", "p3"]  # the clock moves the window, not the facts


def test_a_relevant_role_missing_from_the_document_is_flagged_with_its_unused_achievements() -> None:
    found = issues(BRIEF, doc(("p1", [], ["a1", "a2"])), None, YEAR)
    assert codes(found) == [("missing_position", "Developer at Kubes")] and found[0].fact_ids == ("c1",)


def test_a_role_condensed_under_another_is_not_missing_and_a_letter_has_no_issues() -> None:
    assert issues(BRIEF, doc(("p1", ["p3"], ["a1", "a2"])), None, YEAR) == ()
    assert issues(Brief("letter", FACTS, terms=("Kubernetes",)), doc(), Pages(5, 1.0, 40), YEAR) == ()


def test_a_relevant_role_with_one_bullet_and_achievements_left_is_thin_unless_the_document_is_too_long() -> None:
    thin = doc(("p1", [], ["a1"]), ("p3", [], ["c1"]))
    assert codes(issues(BRIEF, thin, Pages(1, 0.9, 40), YEAR)) == [("thin_position", "Engineer at Acme")]  # p3 has one bullet but nothing left to add
    assert [i.code for i in issues(BRIEF, thin, Pages(2, 0.3, 40), YEAR)] == ["too_long"]


def test_the_length_text_says_how_many_lines_over_or_how_much_room() -> None:
    assert "about 20 lines over" in length_text(Pages(2, 0.5, 40), 1, False)  # type: ignore[operator]
    assert "about 60 lines over" in length_text(Pages(4, 0.5, 40), 2, False)  # type: ignore[operator]
    assert "room for about 20 lines" in length_text(Pages(1, 0.5, 40), 1, True)  # type: ignore[operator]
    assert length_text(Pages(1, 0.5, 40), 1, False) is None  # nothing unused to fill it with
    assert length_text(Pages(1, 0.9, 40), 1, True) is None and length_text(Pages(1, 0.2, 40), 2, True) is None  # full enough; or two pages allowed
    assert "about 1 lines over" in length_text(Pages(2, 0.0, 40), 1, False)  # type: ignore[operator]  # never "0 lines over"


def test_a_one_page_resume_with_room_is_told_so_only_while_relevant_achievements_are_unused() -> None:
    assert [i.code for i in issues(BRIEF, doc(("p1", ["p3"], ["a1", "a2"])), Pages(1, 0.5, 40), YEAR)] == ["room_left"]
    assert issues(BRIEF, doc(("p1", ["p3"], ["a1", "a2", "c1"])), Pages(1, 0.5, 40), YEAR) == ()


def test_next_step_revises_for_an_issue_as_for_a_rejection_and_stops_after_the_one_revision() -> None:
    gap = issues(BRIEF, doc(("p1", [], ["a1", "a2"])), None, YEAR)
    assert next_step(0, Checked(doc(), {}, [], None, gap), False) == "revise"
    assert next_step(1, Checked(doc(), {}, [], None, gap), False) == "end" and next_step(0, Checked(doc(), {}, [], None, gap), True) == "end"
    assert next_step(0, Checked(doc(), {}, [], None, ()), False) == "end"


@given(st.sets(st.sampled_from(["p1", "p2", "p3"])), st.integers(1, 4), st.floats(0, 1), st.integers(1, 80), st.sampled_from([1, 2]))
def test_missing_roles_are_exactly_the_relevant_ones_not_in_the_document_and_over_length_is_flagged_iff_over(held, count, fill, lines, limit) -> None:
    brief = Brief("resume", FACTS, terms=("Kubernetes",), sections=("experience",), caps=Caps(limit, 10))
    own = {"p1": "a1", "p2": "b1", "p3": "c1"}
    found = issues(brief, doc(*((p, [], [own[p]]) for p in sorted(held))), Pages(count, fill, lines), YEAR)
    assert {i.text.split("(")[1].split(")")[0] for i in found if i.code == "missing_position"} == {"p1", "p3"} - held
    assert ("too_long" in [i.code for i in found]) == (count > limit)
    assert all(i.fact_ids == () for i in found if i.code == "too_long") and not any(i.code == "thin_position" for i in found if count > limit)


# --- merged: what a revision may change ---

def test_a_revision_adds_new_bullets_to_their_position_and_a_new_position_as_an_item() -> None:
    previous = doc(("p1", [], ["a1"]))
    submitted = doc(("p1", [], ["a1", "a2"]), ("p3", [], ["c1"]))
    out = merged(previous, submitted, set())
    assert [(slot, text) for slot, text, _ in nodes(out)] == [("bullet:a1", "did a1"), ("bullet:a2", "did a2"), ("bullet:c1", "did c1")]
    assert [i.position_id for i in out.sections[0].items] == ["p1", "p3"]


def test_a_bullet_the_revision_leaves_out_is_kept_unless_the_document_was_over_length() -> None:
    previous, submitted = doc(("p1", [], ["a1", "a2"])), doc(("p1", [], ["a1"]))
    assert [s for s, _, _ in nodes(merged(previous, submitted, set()))] == ["bullet:a1", "bullet:a2"]
    assert [s for s, _, _ in nodes(merged(previous, submitted, set(), over=True))] == ["bullet:a1"]


@given(st.lists(st.sampled_from(["a1", "a2"]), unique=True, min_size=1), st.lists(st.sampled_from(["a1", "a2", "c1"]), unique=True), st.booleans())
def test_merged_never_rewrites_the_text_of_a_slot_it_was_not_asked_to_revise(first, second, over) -> None:
    previous = doc(("p1", [], first))
    submitted = WrittenDocument(sections=(Section(key="experience", items=(Item(position_id="p1", bullets=tuple(Bullet(text="NEW", fact_ids=(a,)) for a in second)),)),))
    before = {s: t for s, t, _ in nodes(previous)}
    after = {s: t for s, t, _ in nodes(merged(previous, submitted, set(), over))}
    assert all(after[s] == before[s] for s in after if s in before)  # a surviving old slot keeps its text
    assert all(s in before or t == "NEW" for s, t in after.items())  # a new slot has the revision's
    assert over or set(before) <= set(after)  # nothing is removed unless over
