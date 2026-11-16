"""ats.check is pure: it compares a Document with an Extracted and reports issues."""

from dataclasses import replace
from itertools import zip_longest

from career_buddy.domain.ats import Extracted, check
from samples import sample_document

DOC = sample_document()


def extracted(lines: list[str], **flags: object) -> Extracted:
    return Extracted(text="\n".join(lines), lines=lines, **flags)  # type: ignore[arg-type]


def codes(ex: Extracted) -> set[str]:
    return {issue.code for issue in check(DOC, ex)}


def wrapped(text: str) -> list[str]:
    """Break a line in two at a word boundary, as a PDF does when it wraps."""
    cut = text.find(" ", len(text) // 2)
    return [text] if cut < 0 else [text[:cut], text[cut + 1 :]]


def test_a_faithful_extraction_passes() -> None:
    assert check(DOC, extracted(DOC.lines())) == []


def test_wrapped_lines_and_bullet_glyphs_still_pass() -> None:
    lines = [f"• {t}" if t.startswith("Cut") else t for t in DOC.lines()]
    lines = [piece for t in lines for piece in wrapped(t)]
    assert check(DOC, extracted(lines)) == []


def test_interleaved_two_column_extraction_fails_ordering() -> None:
    lines = DOC.lines()
    half = len(lines) // 2
    interleaved = [line for pair in zip_longest(lines[:half], lines[half:], fillvalue="") for line in pair if line]
    assert {"order", "headings"} <= codes(extracted(interleaved))


def test_dropped_text_fails_coverage() -> None:
    assert "coverage" in codes(extracted(DOC.lines()[:-3]))


def test_name_must_be_in_the_first_two_lines() -> None:
    lines = DOC.lines()
    assert "name" in codes(extracted(["Résumé", "page 1", *lines]))


def test_structure_flags_each_raise_an_issue() -> None:
    base = extracted(DOC.lines())
    for field, value, code in [
        ("has_tables", True, "table"),
        ("has_text_boxes", True, "text_box"),
        ("header_footer_text", "jane@example.com", "header_footer"),
        ("image_count", 1, "images"),
        ("empty_pages", 1, "text_layer"),
    ]:
        assert codes(replace(base, **{field: value})) == {code}


def test_unmapped_glyphs_fail() -> None:
    lines = [t.replace("Python", "(cid:42)(cid:43)") for t in DOC.lines()]
    assert "glyphs" in codes(extracted(lines))
