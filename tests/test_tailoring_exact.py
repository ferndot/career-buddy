"""Tailoring internals through their public functions: stemming, term weights, ordering, selection, reporting."""

import pytest

from career_graph.domain.profile import PositionView, Profile
from career_graph.domain.tailoring import is_tech, job_terms, stem, tailor
from career_graph.domain.templates import RESUME_CLASSIC, TemplateSpec


@pytest.mark.parametrize(
    ("token", "stemmed"),
    [("Tools", "tool"), ("TEAMS", "team"), ("apps", "app"), ("gas", "gas"), ("go", "go"), ("tank", "tank"),
     ("class", "class"), ("abs", "abs"), ("a", "a")],
)
def test_stem_drops_a_plural_s_from_longer_words_only(token: str, stemmed: str) -> None:
    assert stem(token) == stemmed


@pytest.mark.parametrize(
    ("token", "tech"),
    [("node.js", True), ("C#", True), ("C++", True), ("Spark2", True), ("eBay", True), ("AI", True), ("AWS", True),
     ("A", False), ("Python", False), ("python", False)],
)
def test_is_tech(token: str, tech: bool) -> None:
    assert is_tech(token) is tech


def weights(job: str) -> dict[str, float]:
    return {t.key: t.weight for t in job_terms(job)}


def test_a_plain_first_word_weighs_one() -> None:
    assert weights("Python") == {"python": 1.0}


def test_repeats_add_half_a_point_each_up_to_four() -> None:
    assert weights("go go")["go"] == 1.5
    assert weights("go go go go go go")["go"] == 3.0


def test_a_capital_after_the_first_word_counts_even_if_a_later_use_is_lower_case() -> None:
    assert weights("Use Kafka")["kafka"] == 2.0
    assert weights("we use Kafka and kafka")["kafka"] == 2.5


def test_tech_shape_in_any_use_counts() -> None:
    assert weights("AWS")["aws"] == 2.0
    assert weights("AWS and aws")["aws"] == 2.5


def test_requirements_lines_count_until_the_blank_line() -> None:
    terms = weights("Requirements: Python\n\nwe use python\n\nMust have Rust")
    assert terms["python"] == 3.5 and terms["rust"] == 3.0
    assert weights("Requirements: x1\n\nPython")["python"] == 1.0
    assert weights("Requirements: Python\nand more Python")["python"] == 3.5


def test_terms_after_a_blank_line_are_kept() -> None:
    assert set(weights("Python\n\nRust")) == {"python", "rust"}


def test_single_letters_are_not_terms_but_two_letter_words_are() -> None:
    assert set(weights("Go and R")) == {"go"}


def test_bigrams_are_terms_with_the_capital_and_tech_rules() -> None:
    assert weights("Apache Kafka")["apache kafka"] == 1.0
    assert weights("use Kafka stream")["kafka stream"] == 1.0
    assert weights("use Kafka Streams")["kafka stream"] == 2.0
    assert weights("Spark2 Express")["spark2 express"] == 2.0


def pos(title: str, **attrs: str) -> PositionView:
    return PositionView(title, "Org", attrs)


def order(*positions: PositionView, skills: tuple[str, ...] = ()) -> list[str]:
    profile = Profile(name="X", positions=positions, skills=skills)
    return [p.title for p in tailor(profile, "", RESUME_CLASSIC)[0].positions]


def test_newer_positions_come_first_by_year_then_month() -> None:
    assert order(pos("Jan", finished="2020"), pos("Feb", finished="Feb 2020"), pos("Jun", finished="Jun 2020")) == [
        "Jun", "Feb", "Jan"]
    assert order(pos("Mar", finished="March 2020"), pos("Sep", finished="September 2020")) == ["Sep", "Mar"]


def test_a_later_start_wins_when_the_ends_tie() -> None:
    assert order(pos("Early", started="2018", finished="2020"), pos("Late", started="2019", finished="2020")) == [
        "Late", "Early"]


def test_a_period_is_split_into_start_and_end() -> None:
    assert order(pos("Short", period="2018 - 2019"), pos("Long", period="2018 - 2021")) == ["Long", "Short"]
    assert order(pos("Short", period="2018 to 2019"), pos("Long", period="2018 to 2021")) == ["Long", "Short"]
    assert order(pos("Short", period="2018 – 2019"), pos("Long", period="2018 — 2021")) == ["Long", "Short"]


def test_a_lone_year_is_a_single_year_stint() -> None:
    assert order(pos("Lone", period="2010"), pos("Range", period="2015 - 2016")) == ["Range", "Lone"]


def test_an_undated_position_counts_as_current() -> None:
    assert order(pos("Old", finished="2019"), pos("Undated")) == ["Undated", "Old"]


def test_started_without_an_end_is_current_and_ignores_the_period() -> None:
    assert order(pos("Done", finished="2019"), pos("Open", started="2015", period="1990 - 1991")) == ["Open", "Done"]


def test_a_period_is_used_only_when_there_are_no_started_or_finished_dates() -> None:
    assert order(pos("A", finished="2015", period="2030 - 2031"), pos("B", finished="2017")) == ["B", "A"]


def test_bullet_limits_and_ids() -> None:
    position = PositionView("T", "O", achievements=("a", "b", "c"))
    out, _ = tailor(Profile("X", positions=(position,)), "", TemplateSpec("t", bullets=0))
    assert out.positions[0].achievements == ("a",) and out.positions[0].achievement_ids == ()
    out, _ = tailor(Profile("X", positions=(position,)), "", TemplateSpec("t", bullets=1))
    assert out.positions[0].achievements == ("a",)


def test_skills_matched_by_the_job_come_first_in_job_order() -> None:
    profile = Profile("X", skills=("Alpha", "Zeta", "Mu"), skill_ids=("1", "2", "3"))
    skills, _ = tailor(profile, "Zeta then Alpha", RESUME_CLASSIC)[0].skills, None
    assert skills == ("Zeta", "Alpha", "Mu")
    assert tailor(profile, "Zeta then Alpha", RESUME_CLASSIC)[0].skill_ids == ("2", "1", "3")


def test_a_skill_at_the_very_start_of_the_job_is_matched_once() -> None:
    profile = Profile("X", skills=("Python", "Rust"))
    out = tailor(profile, "Python developer", RESUME_CLASSIC)[0]
    assert out.skills == ("Python", "Rust") and out.skill_ids == ()


def test_the_report_lists_the_heaviest_terms_first() -> None:
    profile = Profile("X", positions=(PositionView("T", "O", achievements=("python rust",)),))
    _, report = tailor(profile, "python rust rust", RESUME_CLASSIC)
    assert report.matched[:2] == ("rust", "python")
