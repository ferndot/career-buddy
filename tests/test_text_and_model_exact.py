"""Small pure helpers: bullet splitting, text normalising and fact ids."""

from career_buddy.domain.model import FactKind, fact_id, normalize
from career_buddy.domain.text import split_bullets


def test_prose_lines_are_joined_with_single_spaces() -> None:
    assert split_bullets("One\nTwo\n- bullet") == (("bullet",), "One Two")


def test_a_bullet_that_starts_with_x_keeps_its_x() -> None:
    assert split_bullets("-Xylophone solo\n•X-ray tech") == (("Xylophone solo", "X-ray tech"), "")


def test_normalize_lowercases_and_collapses_whitespace() -> None:
    assert normalize("  Hello \t WORLD\nAgain ") == "hello world again"


def test_fact_id_ignores_case_and_spacing_and_defaults_to_no_scope() -> None:
    assert fact_id(FactKind.SKILL, "  Go  Lang ") == fact_id(FactKind.SKILL, "go lang", "")
    assert fact_id(FactKind.SKILL, "go") != fact_id(FactKind.SKILL, "go", "x")
