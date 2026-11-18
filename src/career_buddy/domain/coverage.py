"""What the checks made of a written document, and when the writer stops revising. Pure."""

from __future__ import annotations

from dataclasses import dataclass

from career_buddy.domain.generation import Claim, Rejection
from career_buddy.domain.written import WrittenDocument

MAX_REVISIONS = 1  # after the first answer the writer gets one more try: at most two model calls


@dataclass(frozen=True)
class Checked:
    """A validated document with the claims that passed the facts (by slot id) and those that did not."""

    doc: WrittenDocument
    kept: dict[str, Claim]
    rejected: list[Rejection]


def next_step(rounds: int, checked: Checked, failed: bool) -> str:
    """`revise` while something is rejected and a revision is left; `end` otherwise, and always after a failed call."""
    return "revise" if checked.rejected and rounds < MAX_REVISIONS and not failed else "end"
