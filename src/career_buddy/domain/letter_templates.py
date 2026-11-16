"""Cover letter templates. Pure. Facts come from the tailored profile, everything else is fixed wording.

Nothing is invented: a sentence names only what the profile or the user's inputs say, and the rest is boilerplate.
"""

from __future__ import annotations

from collections.abc import Callable

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.profile import Profile

Inputs = dict[str, str]
MAX_BULLETS = 3


def _say(profile: Profile, text: str) -> Entry:
    return Entry(paragraph=Line(text, profile.id or None, Origin.BOILERPLATE))


def _greeting(profile: Profile, who: str) -> Entry:
    return _say(profile, f"Dear {who},")


def _closing(profile: Profile, sign_off: str) -> list[Entry]:
    return [_say(profile, sign_off), _say(profile, profile.name)]


def _lead(profile: Profile) -> str:
    """The most recent position, in plain words. Empty when the profile has none."""
    if not profile.positions:
        return ""
    top = profile.positions[0]
    return f"My most recent role is {top.title} at {top.organization}." if top.organization else f"My most recent role is {top.title}."


def _bullets(profile: Profile) -> tuple[Line, ...]:
    rows = [(text, aid or p.id or None) for p in profile.positions
            for text, aid in zip(p.achievements, p.achievement_ids or (None,) * len(p.achievements))]
    return tuple(Line(text, source) for text, source in rows[:MAX_BULLETS])


def _skills(profile: Profile) -> str:
    return f"My experience includes {', '.join(profile.skills)}." if profile.skills else ""


def _letter(profile: Profile, label: str, body: list[Entry]) -> Document:
    person = profile.id or None
    place = profile.attributes.get("location", "")
    return Document(Line(profile.name, person), (Line(place, person),) if place else (),
                    (Section("", tuple(body)),), label)


def _join(*sentences: str) -> str:
    return " ".join(s for s in sentences if s)


def cover_letter(profile: Profile, inputs: Inputs) -> Document:
    role, company = inputs["role"], inputs["company"]
    bullets = _bullets(profile)
    body = [
        _greeting(profile, inputs.get("recipient") or "Hiring Team"),
        _say(profile, _join(f"I am writing to apply for the {role} position at {company}.", _lead(profile))),
    ]
    if bullets:
        body.append(Entry(paragraph=Line("Some of the work I would bring to this role:", profile.id or None,
                                         Origin.BOILERPLATE), bullets=bullets))
    if skills := _skills(profile):
        body.append(_say(profile, skills))
    body.append(_say(profile, "Thank you for your consideration. I would welcome the chance to discuss the role with you."))
    return _letter(profile, "Cover Letter", body + _closing(profile, "Sincerely,"))


def cover_letter_email(profile: Profile, inputs: Inputs) -> Document:
    role, company = inputs["role"], inputs["company"]
    body = [
        _say(profile, f"Subject: Application for the {role} position at {company}"),
        _greeting(profile, inputs.get("recipient") or "Hiring Team"),
        _say(profile, _join(f"I am applying for the {role} position at {company}.", _lead(profile), _skills(profile))),
        _say(profile, "Thank you for your time. I look forward to hearing from you."),
    ]
    return _letter(profile, "Cover Letter Email", body + _closing(profile, "Best regards,"))


LETTERS: dict[str, Callable[[Profile, Inputs], Document]] = {
    "cover-letter": cover_letter,
    "cover-letter-email": cover_letter_email,
}
