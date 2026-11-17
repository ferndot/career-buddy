"""General rules for a resume and for a letter: what good ones look like. Pure data.

These shape style and selection only. The grounding rules (use only the facts, cite them) are the writer's own prompt and are not
here. A rule is one plain sentence for the model; a document kind's rules are a tuple of them, so a person's own set can replace
a default (Settings, later) and travel in `Brief.rules`.
"""

from __future__ import annotations

from typing import Literal

RESUME_RULES: tuple[str, ...] = (
    'Plain headings: Summary, Experience, Education, Skills. One date format throughout, such as "Jan 2022 – Mar 2024".',
    "Each role gets 3 to 6 bullets: about 5 to 8 for the current or most relevant role, 1 to 3 for older or unrelated ones. A bullet is one or two lines.",
    "Open each bullet with a strong action verb, and vary the verbs across the resume. Quantify results where the facts give numbers; where they do not, state the outcome.",
    'Give the most space to recent, relevant experience. Cover about the last 10 to 15 years: condense older roles into one short "Earlier" line, or leave them out when they do not help for this role; leave out roles older than about 15 years unless they are directly relevant.',
    "Length: one page under about 10 years of experience, two pages for 10 or more years or a senior candidate. The template's length instruction governs; these are defaults.",
    "No claim beyond the facts, and no invented numbers.",
)

LETTER_RULES: tuple[str, ...] = (
    "About 250 to 400 words in three or four short paragraphs: open with the role and who you are, one or two paragraphs of proof, then close by asking for an interview.",
    "Do not repeat the resume. Use the exact company and role title from the posting.",
    'No clichés such as "outside the box". No "To Whom It May Concern" and no "Dear Sir or Madam". No greeting or sign-off unless the template asks for one.',
)

DEFAULT_RULES: dict[Literal["resume", "letter"], tuple[str, ...]] = {"resume": RESUME_RULES, "letter": LETTER_RULES}


def rules_text(rules: tuple[str, ...], kind: str) -> str:
    """The rules as the system message states them. Empty when there are none. A cap or a length the template gives is more specific, so it wins."""
    if not rules:
        return ""
    return (f"General rules for a {kind} (defaults: the template's instructions and the length below win where they differ; they never allow a fact that is not given):\n"
            + "\n".join(f"- {r}" for r in rules))
