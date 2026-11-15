"""Letter and LinkedIn-About templates. Pure. Facts come from the tailored profile, everything else is fixed wording.

Nothing is invented: a sentence names only what the profile or the user's inputs say, and the rest is boilerplate.
"""

from __future__ import annotations

from collections.abc import Callable

from career_graph.domain.document import Document, Entry, Line, Origin, Section
from career_graph.domain.profile import Profile

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


def _letter(profile: Profile, label: str, body: list[Entry], with_place: bool = True) -> Document:
    person = profile.id or None
    place = profile.attributes.get("location", "") if with_place else ""
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


def thank_you(profile: Profile, inputs: Inputs) -> Document:
    role, company = inputs["role"], inputs["company"]
    body = [
        _greeting(profile, inputs["interviewer"]),
        _say(profile, f"Thank you for speaking with me on {inputs['interview_date']} about the {role} position at "
                      f"{company}. I enjoyed our conversation and remain interested in the role."),
        _say(profile, _join(_lead(profile), _skills(profile))),
        _say(profile, "Please let me know if I can provide anything further."),
    ]
    return _letter(profile, "Thank You", [e for e in body if e.paragraph.text] + _closing(profile, "Sincerely,"))


def follow_up(profile: Profile, inputs: Inputs) -> Document:
    role, company = inputs["role"], inputs["company"]
    body = [
        _greeting(profile, inputs.get("recipient") or "Hiring Team"),
        _say(profile, f"I applied for the {role} position at {company} on {inputs['applied_date']} and am writing to "
                      "follow up on my application. I remain interested in the role."),
        _say(profile, _join(_lead(profile), _skills(profile))),
        _say(profile, "Thank you for your time. I look forward to hearing from you."),
    ]
    return _letter(profile, "Follow Up", [e for e in body if e.paragraph.text] + _closing(profile, "Sincerely,"))


def linkedin_about(profile: Profile, inputs: Inputs) -> Document:
    person = profile.id or None
    intro = profile.attributes.get("summary") or profile.attributes.get("headline") or _lead(profile)
    body = [_say(profile, intro)] if intro else []
    if bullets := _bullets(profile):
        body.append(Entry(paragraph=Line("Highlights:", person, Origin.BOILERPLATE), bullets=bullets))
    if profile.skills:
        body.append(_say(profile, f"Skills: {', '.join(profile.skills)}"))
    return _letter(profile, "LinkedIn About", body, with_place=False)


LETTERS: dict[str, Callable[[Profile, Inputs], Document]] = {
    "cover-letter": cover_letter,
    "cover-letter-email": cover_letter_email,
    "thank-you": thank_you,
    "follow-up": follow_up,
    "linkedin-about": linkedin_about,
}
