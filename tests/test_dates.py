"""Partial dates ("2021", "2021-03", "2021-03-14"): parsing, display, and reading the free text of a source."""

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from career_buddy.domain.dates import checked, dates_from_text, format_date, format_range, parse, read_bounds
from career_buddy.domain.model import InvalidFact

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


@st.composite
def partial_dates(draw):
    """(iso text, precision 1-3, the date it was cut from)"""
    day = draw(st.dates(min_value=date(1, 1, 1)))
    precision = draw(st.integers(1, 3))
    return day.isoformat()[: (4, 7, 10)[precision - 1]], precision, day


@given(partial_dates())
def test_parse_keeps_the_precision_and_the_values(case) -> None:
    text, precision, day = case
    assert parse(text) == (day.year, day.month, day.day)[:precision]


@given(partial_dates())
def test_the_display_names_the_same_year_month_and_day(case) -> None:
    text, precision, day = case
    shown = format_date(text).split()
    assert len(shown) == precision and shown[-1] == f"{day.year:04d}"
    if precision > 1:
        assert shown[-2] == MONTHS[day.month - 1]
    if precision == 3:
        assert shown[0] == str(day.day)


@given(st.text(max_size=20))
def test_only_exact_partial_iso_text_is_a_date(text: str) -> None:
    parts = parse(text)
    assert parts is None or text == "-".join([f"{parts[0]:04d}", *(f"{p:02d}" for p in parts[1:])])


@given(st.text(max_size=20))
def test_text_that_is_no_date_is_shown_as_written(text: str) -> None:
    if parse(text) is None and text.lower() != "present":
        assert format_date(text) == text


@given(st.text(max_size=30))
def test_checked_never_stores_a_bound_that_is_not_a_date(text: str) -> None:
    try:
        out = checked({"started": text})
    except InvalidFact:
        return
    assert "started" not in out or parse(out["started"]) is not None


@pytest.mark.parametrize("bad", ["21", "2021-3", "2021-13", "2021-02-30", "2021/03", "2021-03-", "0000", "٢٠٢١", "present"])
def test_invalid_start_is_rejected(bad: str) -> None:
    with pytest.raises(InvalidFact):
        checked({"started": bad})


def test_present_is_an_end_but_not_a_start_and_the_end_may_not_precede_the_start() -> None:
    assert checked({"started": "2019-03", "finished": " Present "}) == {"started": "2019-03", "finished": "present"}
    with pytest.raises(InvalidFact):
        checked({"started": "2021", "finished": "2019-12"})
    assert checked({"started": "2019-06", "finished": "2019"})  # a year-only end covers the whole year


def test_display_formats() -> None:
    assert [format_date(d) for d in ("2019", "2019-03", "2019-03-14", "present")] == ["2019", "Mar 2019", "14 Mar 2019", "Present"]
    assert format_range("2019", "2021") == "2019 – 2021"
    assert format_range("2019-03", "present") == "Mar 2019 – Present"
    assert format_range("2019-03", "") == "Mar 2019 – Present"
    assert format_range("2019", "2019") == "2019"
    assert format_range("", "2019-03-14") == "14 Mar 2019"
    assert format_range("", "") == ""


@pytest.mark.parametrize(
    ("text", "dates"),
    [
        ("2019 - 2021", {"started": "2019", "finished": "2021"}),
        ("2012-2013", {"started": "2012", "finished": "2013"}),
        ("Mar 2019 – Present", {"started": "2019-03", "finished": "present"}),
        ("March 2019 to Sept 2020", {"started": "2019-03", "finished": "2020-09"}),
        ("2019", {"started": "2019", "finished": "2019"}),
        ("2019 -", {"started": "2019", "finished": "present"}),
        ("- 2015", {"finished": "2015"}),
    ],
)
def test_clear_source_text_becomes_dates(text: str, dates: dict) -> None:
    assert dates_from_text(text) == dates


@pytest.mark.parametrize("text", ["", "a while ago", "Spring 2019 - 2020", "Marketing 2019", "2021 - 2019", "2019 - 2020 - 2021", "-", "Present"])
def test_unclear_source_text_gives_no_dates(text: str) -> None:
    assert dates_from_text(text) == {}


def test_started_and_finished_written_as_text_are_read_and_unclear_text_gives_none() -> None:
    assert read_bounds({"started": "Mar 2019", "finished": "Jan 2023"}) == {"started": "2019-03", "finished": "2023-01"}
    assert read_bounds({"started": "2019", "finished": "Current"}) == {"started": "2019", "finished": "present"}
    assert read_bounds({"started": "Spring 2019", "finished": "2020"}) == {}
    assert read_bounds({}, "2019 - 2021") == {"started": "2019", "finished": "2021"}


@given(st.dictionaries(st.sampled_from(["started", "finished"]), st.text(max_size=25), max_size=2), st.text(max_size=25))
def test_reading_dates_twice_changes_nothing_more(raw: dict, fallback: str) -> None:
    once = read_bounds(raw, fallback)
    assert read_bounds(once) == once
    assert all(parse(v) or v == "present" for v in once.values())
