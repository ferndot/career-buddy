"""Templates are data (plan D2): a spec says which sections appear and in what order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from career_buddy.domain.dates import format_range
from career_buddy.domain.document import Document, Entry, Line, Section
from career_buddy.domain.letter_templates import LETTERS
from career_buddy.domain.profile import PositionView, Profile


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    label: str = ""  # shown in the template picker
    sections: tuple[tuple[str, str], ...] = ()  # resumes: (section key, fixed ATS heading label)
    bullets: int = 5  # most bullets kept per position
    skills: int = 15  # most skills listed
    kind: Literal["resume", "letter"] = "resume"
    required: tuple[str, ...] = ()  # input names the caller must give
    optional: tuple[str, ...] = ()


_SUMMARY, _EXPERIENCE, _EDUCATION, _SKILLS = (
    ("summary", "Summary"), ("experience", "Experience"), ("education", "Education"), ("skills", "Skills"))
RESUME_CLASSIC = TemplateSpec("resume-classic", "Classic resume", (_SUMMARY, _EXPERIENCE, _EDUCATION, _SKILLS))
RESUME_COMPACT = TemplateSpec("resume-compact", "Compact resume", RESUME_CLASSIC.sections, bullets=3, skills=10)
RESUME_HYBRID = TemplateSpec("resume-hybrid", "Hybrid resume", (_SUMMARY, _SKILLS, _EXPERIENCE, _EDUCATION))
_JOB = ("company", "role")


def _letter(id: str, label: str, optional: tuple[str, ...] = ()) -> TemplateSpec:
    return TemplateSpec(id, label, bullets=2, skills=5, kind="letter", required=_JOB, optional=optional)


TEMPLATES = (
    RESUME_CLASSIC,
    RESUME_COMPACT,
    RESUME_HYBRID,
    _letter("cover-letter", "Cover letter", optional=("recipient",)),
    _letter("cover-letter-email", "Cover letter (email)", optional=("recipient",)),
)
_REGISTRY = {spec.id: spec for spec in TEMPLATES}


def get_template(template_id: str) -> TemplateSpec:
    return _REGISTRY[template_id]


def _period(pos: PositionView) -> str:
    return format_range(pos.attributes.get("started", ""), pos.attributes.get("finished", ""))


def position_heading(pos: PositionView) -> str:
    period = _period(pos)
    heading = f"{pos.title}, {pos.organization}" if pos.organization else pos.title
    return f"{heading} ({period})" if period else heading


def _position(pos: PositionView) -> Entry:
    source = pos.id or None
    ids = pos.achievement_ids or (None,) * len(pos.achievements)
    return Entry(
        heading=Line(position_heading(pos), source, field="heading" if source else ""),
        bullets=tuple(Line(a, aid or source, field="title" if aid else "") for a, aid in zip(pos.achievements, ids)),
    )


def _own(profile: Profile, field: str) -> str:
    """The person's field a line shows. Empty without a person fact: such a line is fixed wording."""
    return field if profile.id else ""


def _sections(profile: Profile) -> dict[str, tuple[Entry, ...]]:
    summary = profile.attributes.get("summary", "")
    return {
        "summary": (Entry(paragraph=Line(summary, profile.id or None, field=_own(profile, "summary"))),) if summary else (),
        "experience": tuple(_position(p) for p in profile.positions),
        "education": (
            (Entry(bullets=tuple(Line(e.label, e.id or None, field="label" if e.id else "") for e in profile.education)),)
            if profile.education else ()
        ),
        "skills": (Entry(paragraph=Line(", ".join(profile.skills), profile.id or None, field="skills" if profile.skill_ids else "",
                                        cites=profile.skill_ids)),) if profile.skills else (),
    }


def build_document(profile: Profile, spec: TemplateSpec, inputs: dict[str, str] | None = None) -> Document:
    if spec.kind != "resume":
        return LETTERS[spec.id](profile, inputs or {})
    available = _sections(profile)
    sections = tuple(Section(label, available[key]) for key, label in spec.sections if available[key])
    person = profile.id or None
    contact = profile.attributes.get("location", "")
    headline = profile.attributes.get("headline", "")
    intro = tuple(Line(text, person, field=_own(profile, name)) for name, text in (("location", contact), ("headline", headline)) if text)
    return Document(Line(profile.name, person, field=_own(profile, "title")), intro, sections)
