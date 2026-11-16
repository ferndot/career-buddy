"""ats.check, pinned to its exact issues and messages."""

from career_buddy.domain.ats import Extracted, Issue, check
from career_buddy.domain.document import Document, Entry, Line, Section

LINES = ["Ann Lee", "Experience", "Built A", "Built B"]
DOC = Document(Line("Ann Lee"), (), (Section("Experience", (Entry(bullets=(Line("Built A"), Line("Built B"))),)),))


def read(text: str, lines: list[str] | None = None, **flags: object) -> list[Issue]:
    return check(DOC, Extracted(text, LINES if lines is None else lines, **flags))  # type: ignore[arg-type]


def test_a_missing_line_reports_how_many_were_read_back() -> None:
    assert read("Ann Lee Experience Built A") == [Issue("coverage", "Only 3 of 4 lines were read back")]


def test_coverage_exactly_at_the_threshold_passes() -> None:
    bullets = tuple(Line(f"item{n:02d}") for n in range(48))
    doc = Document(Line("Ann Lee"), (), (Section("Experience", (Entry(bullets=bullets),)),))
    seen = [b.text for b in bullets[:-1]]  # 49 of 50 lines come back: 0.98, the minimum
    lines = ["Ann Lee", "Experience", *seen]
    assert check(doc, Extracted(" ".join(lines), lines)) == []


def test_out_of_order_lines_name_the_first_offender() -> None:
    issues = read("Ann Lee Experience Built C Built B Built A", ["Ann Lee", "Experience", "Built A", "Built B"])
    assert issues == [Issue("order", "Lines out of reading order, first: 'Built B'")]


def test_a_repeated_line_is_matched_at_its_first_place_in_reading_order() -> None:
    assert read("Ann Lee Experience Built A Built B Built A") == []


def test_every_structural_problem_has_its_message() -> None:
    issues = read("Ann Lee Experience Built A Built B (cid:3)", ["Built A", "Built B", "Ann Lee"],
                  has_tables=True, has_text_boxes=True, header_footer_text="Page 1", image_count=1, empty_pages=1)
    assert issues == [
        Issue("name", "The name is not in the first two lines"),
        Issue("headings", "Section headings are missing or out of template order"),
        Issue("table", "Contains a table"),
        Issue("text_box", "Contains a text box"),
        Issue("header_footer", "Text sits in the header or footer"),
        Issue("images", "Contains images"),
        Issue("text_layer", "A page has no text layer"),
        Issue("glyphs", "Unmapped glyphs in the text layer"),
    ]


def test_an_out_of_order_line_counts_once_toward_coverage() -> None:
    assert read("Ann Lee Built B Experience") == [
        Issue("coverage", "Only 3 of 4 lines were read back"),
        Issue("order", "Lines out of reading order, first: 'Built B'"),
    ]
