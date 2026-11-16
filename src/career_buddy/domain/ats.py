"""ATS compatibility check: compares what we meant to print with what a text extractor reads back."""

from __future__ import annotations

from dataclasses import dataclass, field

from career_buddy.domain.document import Document


@dataclass(frozen=True)
class Extracted:
    """What a parser sees in a file. Produced by a TextReader, consumed by `check`."""

    text: str
    lines: list[str] = field(default_factory=list)
    has_tables: bool = False
    has_text_boxes: bool = False
    header_footer_text: str = ""
    image_count: int = 0
    empty_pages: int = 0  # pages with no text layer (PDF)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


MIN_COVERAGE = 0.98


def _norm(text: str) -> str:
    return " ".join(text.split())


def _headings_in_order(headings: list[str], lines: list[str]) -> bool:
    """True when each heading is a line of its own and they appear in template order."""
    remaining = iter(_norm(line) for line in lines)
    return all(any(line == heading for line in remaining) for heading in headings)


def check(expected: Document, extracted: Extracted) -> list[Issue]:
    """Issues that would trip an ATS parser. An empty list means the file passes."""
    issues: list[Issue] = []
    stream = _norm(extracted.text)
    want = [_norm(line) for line in expected.lines()]

    found = cursor = 0
    out_of_order: list[str] = []
    for line in want:
        at = stream.find(line, cursor)
        if at >= 0:
            found, cursor = found + 1, at + len(line)
        elif line in stream:
            found += 1
            out_of_order.append(line)
    if want and found / len(want) < MIN_COVERAGE:
        issues.append(Issue("coverage", f"Only {found} of {len(want)} lines were read back"))
    if out_of_order:
        issues.append(Issue("order", f"Lines out of reading order, first: {out_of_order[0]!r}"))

    if _norm(expected.name.text) not in _norm(" ".join(extracted.lines[:2])):
        issues.append(Issue("name", "The name is not in the first two lines"))
    if not _headings_in_order([_norm(h) for h in expected.headings()], extracted.lines):
        issues.append(Issue("headings", "Section headings are missing or out of template order"))

    for flag, code, message in (
        (extracted.has_tables, "table", "Contains a table"),
        (extracted.has_text_boxes, "text_box", "Contains a text box"),
        (bool(extracted.header_footer_text), "header_footer", "Text sits in the header or footer"),
        (extracted.image_count > 0, "images", "Contains images"),
        (extracted.empty_pages > 0, "text_layer", "A page has no text layer"),
        ("(cid:" in extracted.text, "glyphs", "Unmapped glyphs in the text layer"),
    ):
        if flag:
            issues.append(Issue(code, message))
    return issues
