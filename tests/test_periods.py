"""Career periods: the year span read from the text, and overlap between two stints."""

from hypothesis import given
from hypothesis import strategies as st

from career_buddy.domain.periods import Period, period_of


def test_a_year_range_open_range_and_end_only_range() -> None:
    assert period_of({"period": "2019 - 2021"}) == Period(2019, 2021)
    assert period_of({"period": "Jan 2020 - Present"}) == Period(2020, float("inf"))
    assert period_of({"period": "- 2015"}) == Period(float("-inf"), 2015)


def test_started_and_finished_are_read_when_there_is_no_period_text() -> None:
    assert period_of({"started": "2010", "finished": "2012"}) == Period(2010, 2012)


def test_no_year_means_no_period() -> None:
    assert period_of({"period": "a while ago"}) is None
    assert period_of({}) is None


@given(st.text(max_size=60))
def test_any_text_either_gives_no_period_or_an_ordered_one(text: str) -> None:
    period = period_of({"period": text})
    assert period is None or period.start <= period.end


@given(st.integers(1950, 2050), st.integers(0, 30), st.integers(1950, 2050), st.integers(0, 30))
def test_overlap_is_symmetric_and_matches_the_year_intervals(a: int, da: int, b: int, db: int) -> None:
    p, q = Period(a, a + da), Period(b, b + db)
    assert p.overlaps(q) == q.overlaps(p)
    assert p.overlaps(q) == (max(a, b) <= min(a + da, b + db))


def test_years_given_backwards_are_read_as_a_span() -> None:
    assert period_of({"period": "2021 - 2019"}) == Period(2019, 2021)
