"""One line of a skills section becomes separate skills."""

from hypothesis import given, strategies as st

from career_graph.domain.text import SKILL_SEPARATORS, split_skills


def test_commas_semicolons_pipes_bullets_and_pdf_glyphs_all_separate_skills() -> None:
    assert split_skills("Python, Go; SQL | Kafka • AWS · Docker \ufffd Terraform") == [
        "Python", "Go", "SQL", "Kafka", "AWS", "Docker", "Terraform",
    ]


def test_separators_inside_brackets_do_not_split() -> None:
    assert split_skills("Python (3.11, pandas), Go") == ["Python (3.11, pandas)", "Go"]


def test_bullets_trailing_full_stops_and_blanks_are_removed() -> None:
    assert split_skills("- Python., , Go.  ") == ["Python", "Go"]


def test_exact_repeats_keep_the_first_wording_once() -> None:
    assert split_skills("Python, Go, Python") == ["Python", "Go"]


def test_slashes_and_hyphens_inside_a_name_are_kept() -> None:
    assert split_skills("CI/CD, Node.js, Spring-Boot") == ["CI/CD", "Node.js", "Spring-Boot"]


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=80))
def test_no_skill_is_empty_or_holds_a_top_level_separator(line: str) -> None:
    skills = split_skills(line)
    assert all(s and s == s.strip() for s in skills)
    assert all(not any(ch in SKILL_SEPARATORS for ch in s) or "(" in s for s in skills)
    assert len(skills) == len({s for s in skills})
