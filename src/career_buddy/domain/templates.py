"""Templates are data (plan D2): a spec says which sections appear and in what order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from career_buddy.domain.dates import format_range
from career_buddy.domain.document import Document, Entry, Line, Section
from career_buddy.domain.profile import PositionView, Profile


@dataclass(frozen=True)
class Layout:
    """How a template arranges its page. Data: the stored html wraps its parts in these classes and `css` styles them
    (adapters/outputs/render_html.py); the wizard draws the same arrangement from it.

    `side` are the headings of trailing sections that sit in a side column beside the rest."""

    header: Literal["plain", "centered", "band"] = "plain"
    side: tuple[str, ...] = ()
    css: str = ""


@dataclass(frozen=True)
class WritingStyle:
    """A way to write a letter, picked on the template step. Its instructions go to the writer after the template's own."""

    id: str
    label: str
    instructions: str


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    label: str = ""  # shown in the template picker
    sections: tuple[tuple[str, str], ...] = ()  # resumes: (section key, fixed ATS heading label)
    kind: Literal["resume", "letter"] = "resume"
    required: tuple[str, ...] = ()  # input names the caller must give
    optional: tuple[str, ...] = ()
    layout: Layout = Layout()
    instructions: str = ""  # what the writer is told about this template's style
    styles: tuple[WritingStyle, ...] = ()  # a letter's suggested styles, each with its own instructions


_SUMMARY, _EXPERIENCE, _EDUCATION, _SKILLS = (
    ("summary", "Summary"), ("experience", "Experience"), ("education", "Education"), ("skills", "Skills"))
_ALL = (_SUMMARY, _EXPERIENCE, _EDUCATION, _SKILLS)
_BAND = "header{background:#1f3a5f;color:#fff;padding:.8rem 1rem}header p{margin:0;color:#dbe6f4}"
RESUME_CLASSIC = TemplateSpec(
    "resume-classic", "Classic resume", _ALL,
    layout=Layout("centered", css="header{text-align:center;margin-bottom:.5rem}"
                  "h2{border-bottom:1px solid #222;text-transform:uppercase;font-size:11pt;letter-spacing:.06em}"),
    instructions="Traditional single-column resume. Formal, conventional wording; a two or three sentence summary; every bullet starts with a past-tense action verb and fits one line.",
)
RESUME_SIDEBAR = TemplateSpec(
    "resume-sidebar", "Sidebar resume", _ALL,
    layout=Layout("plain", ("Education", "Skills"),
                  ".cols{display:flex;gap:1.5rem}.main{flex:1 1 68%}.side{flex:0 0 28%;background:#f2f4f7;padding:.4rem .8rem}"
                  "header{border-bottom:3px solid #2b5c8a;margin-bottom:.6rem}h2{color:#2b5c8a;font-size:12pt}"),
    instructions="Two-column resume: the narrow side column holds skills and education, so keep the summary to two sentences and every bullet under about 15 words, with at most three bullets for each position.",
)
RESUME_MODERN = TemplateSpec(
    "resume-modern", "Modern resume", _ALL,
    layout=Layout("band", css=_BAND + "header{margin-bottom:.6rem}h2{color:#1f3a5f;font-size:11pt;text-transform:uppercase}body{font-size:10.5pt}"),
    instructions="Compact modern resume. A one or two sentence summary that leads with the strongest proof. Tight bullets that open with the outcome and then say how; no filler.",
)

LETTER_STYLES = (
    WritingStyle("direct", "Direct and concise",
                 "Direct and concise: three short paragraphs, about 150 to 200 words in all. Open with the role and the single strongest match, give one proof, close with a short ask. No pleasantries."),
    WritingStyle("narrative", "Narrative story",
                 "Narrative story: open with one concrete moment from the facts that shows why the person fits, tell it in plain first-person prose, then connect it to the role. Four paragraphs, warm and specific."),
    WritingStyle("formal", "Formal traditional",
                 "Formal and traditional: a measured, polite business register in full sentences, with no contractions. Four paragraphs: interest in the role, qualifications, one achievement, a courteous close."),
)


def _letter(id: str, label: str, layout: Layout, instructions: str) -> TemplateSpec:
    """A job-board letter: the company and role are read from the posting, not asked for."""
    return TemplateSpec(id, label, kind="letter", optional=("recipient",), layout=layout, instructions=instructions, styles=LETTER_STYLES)


TEMPLATES = (
    RESUME_CLASSIC,
    RESUME_SIDEBAR,
    RESUME_MODERN,
    _letter("cover-letter", "Classic cover letter", Layout("plain", css="header{margin-bottom:1.2rem}p{margin:.6rem 0}"),
            "Classic letter layout: plain paragraphs under the applicant's name."),
    _letter("cover-letter-modern", "Modern cover letter", Layout("band", css=_BAND + "header{margin-bottom:1.2rem}p{margin:.6rem 0}"),
            "Modern letter with a header band: short, conversational paragraphs."),
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
    """A resume from the facts. A letter is only its header and an empty body: its text comes from a writer or the user."""
    person = profile.id or None
    letter = spec.kind == "letter"
    header = ("location",) if letter else ("location", "headline")
    intro = tuple(Line(text, person, field=_own(profile, name)) for name in header if (text := profile.attributes.get(name, "")))
    name = Line(profile.name, person, field=_own(profile, "title"))
    if letter:
        return Document(name, intro, (Section("", ()),), "Cover Letter")  # the inputs (company, role) are for the writer
    available = _sections(profile)
    return Document(name, intro, tuple(Section(label, available[key]) for key, label in spec.sections if available[key]))
