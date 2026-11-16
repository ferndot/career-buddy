"""Letter templates, checked for their exact output (wording, line sources, origins) through `build_document`."""

import pytest

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.letter import write_letter
from career_buddy.domain.profile import PositionView, Profile
from career_buddy.domain.templates import build_document, get_template

PID = "pid"
FULL = Profile(
    name="Ada Lovelace",
    id=PID,
    attributes={"location": "London", "summary": "Mathematician.", "headline": "Analyst"},
    positions=(
        PositionView("Engineer", "Acme", achievements=("Built A", "Built B"), achievement_ids=("a1", "a2"), id="p1"),
        PositionView("Analyst", "Beta", achievements=("Did X", "Did Y"), id="p2"),
    ),
    skills=("Python", "Go"),
)
BARE = Profile(name="Bob")
NO_ORG = Profile(name="Cy", id="c", positions=(PositionView("Chef", ""),))
JOB = {"role": "Dev", "company": "Initech"}
LEAD = "My most recent role is Engineer at Acme."
SKILLS = "My experience includes Python, Go."
BULLETS = (Line("Built A", "a1"), Line("Built B", "a2"), Line("Did X", "p2"))


def say(text: str, source: str | None = PID) -> Entry:
    return Entry(paragraph=Line(text, source, Origin.BOILERPLATE))


def letter(profile: Profile, label: str, body: list[Entry], place: str = "London", source: str | None = PID) -> Document:
    intro = (Line(place, source),) if place else ()
    return Document(Line(profile.name, source), intro, (Section("", tuple(body)),), label)


def build(template: str, profile: Profile, **inputs: str) -> Document:
    return build_document(profile, get_template(template), inputs)


def test_cover_letter_full() -> None:
    expected = letter(FULL, "Cover Letter", [
        say("Dear Ann,"),
        say(f"I am writing to apply for the Dev position at Initech. {LEAD}"),
        Entry(paragraph=Line("Some of the work I would bring to this role:", PID, Origin.BOILERPLATE), bullets=BULLETS),
        say(SKILLS),
        say("Thank you for your consideration. I would welcome the chance to discuss the role with you."),
        say("Sincerely,"),
        say("Ada Lovelace"),
    ])
    assert build("cover-letter", FULL, recipient="Ann", **JOB) == expected


def test_cover_letter_defaults_to_hiring_team_and_skips_what_the_profile_lacks() -> None:
    expected = letter(BARE, "Cover Letter", [
        say("Dear Hiring Team,", None),
        say("I am writing to apply for the Dev position at Initech.", None),
        say("Thank you for your consideration. I would welcome the chance to discuss the role with you.", None),
        say("Sincerely,", None),
        say("Bob", None),
    ], place="", source=None)
    assert build("cover-letter", BARE, **JOB) == expected


def test_lead_names_only_the_title_when_there_is_no_organization() -> None:
    doc = build("cover-letter", NO_ORG, **JOB)
    assert doc.sections[0].entries[1].paragraph.text == (
        "I am writing to apply for the Dev position at Initech. My most recent role is Chef.")


def test_cover_letter_email_full() -> None:
    expected = letter(FULL, "Cover Letter Email", [
        say("Subject: Application for the Dev position at Initech"),
        say("Dear Ann,"),
        say(f"I am applying for the Dev position at Initech. {LEAD} {SKILLS}"),
        say("Thank you for your time. I look forward to hearing from you."),
        say("Best regards,"),
        say("Ada Lovelace"),
    ])
    assert build("cover-letter-email", FULL, recipient="Ann", **JOB) == expected


def test_cover_letter_email_bare_profile() -> None:
    doc = build("cover-letter-email", BARE, **JOB)
    assert [e.paragraph.text for e in doc.sections[0].entries] == [
        "Subject: Application for the Dev position at Initech", "Dear Hiring Team,",
        "I am applying for the Dev position at Initech.",
        "Thank you for your time. I look forward to hearing from you.", "Best regards,", "Bob"]


def test_thank_you_full_and_bare() -> None:
    inputs = {**JOB, "interviewer": "Dr. Who", "interview_date": "May 5"}
    thanks = "Thank you for speaking with me on May 5 about the Dev position at Initech. " \
             "I enjoyed our conversation and remain interested in the role."
    expected = letter(FULL, "Thank You", [
        say("Dear Dr. Who,"), say(thanks), say(f"{LEAD} {SKILLS}"),
        say("Please let me know if I can provide anything further."), say("Sincerely,"), say("Ada Lovelace"),
    ])
    assert build("thank-you", FULL, **inputs) == expected
    bare = build("thank-you", BARE, **inputs)
    assert [e.paragraph.text for e in bare.sections[0].entries] == [
        "Dear Dr. Who,", thanks, "Please let me know if I can provide anything further.", "Sincerely,", "Bob"]


def test_follow_up_full_and_bare() -> None:
    inputs = {**JOB, "applied_date": "May 1"}
    ask = ("I applied for the Dev position at Initech on May 1 and am writing to follow up on my application. "
           "I remain interested in the role.")
    expected = letter(FULL, "Follow Up", [
        say("Dear Ann,"), say(ask), say(f"{LEAD} {SKILLS}"),
        say("Thank you for your time. I look forward to hearing from you."), say("Sincerely,"), say("Ada Lovelace"),
    ])
    assert build("follow-up", FULL, recipient="Ann", **inputs) == expected
    bare = build("follow-up", BARE, **inputs)
    assert [e.paragraph.text for e in bare.sections[0].entries] == [
        "Dear Hiring Team,", ask, "Thank you for your time. I look forward to hearing from you.", "Sincerely,", "Bob"]


def test_linkedin_about_prefers_summary_then_headline_then_the_lead() -> None:
    expected = letter(FULL, "LinkedIn About", [
        say("Mathematician."),
        Entry(paragraph=Line("Highlights:", PID, Origin.BOILERPLATE), bullets=BULLETS),
        say("Skills: Python, Go"),
    ], place="")
    assert build("linkedin-about", FULL) == expected
    headline_only = Profile(name="Q", id="q", attributes={"headline": "Analyst"}, positions=FULL.positions)
    assert build("linkedin-about", headline_only).sections[0].entries[0] == say("Analyst", "q")
    lead_only = Profile(name="Q", id="q", positions=FULL.positions)
    assert build("linkedin-about", lead_only).sections[0].entries[0] == say(LEAD, "q")
    summary_and_headline = Profile(name="Q", attributes={"summary": "S", "headline": "H"})
    assert build("linkedin-about", summary_and_headline).sections[0].entries == (say("S", None),)


def test_linkedin_about_of_an_empty_profile_has_no_body() -> None:
    doc = build("linkedin-about", BARE)
    assert doc == Document(Line("Bob", None), (), (Section("", ()),), "LinkedIn About")


def test_cover_letter_keeps_at_most_three_bullets() -> None:
    many = Profile(name="M", positions=(PositionView("T", "O", achievements=("1", "2", "3", "4")),))
    entry = build("cover-letter", many, **JOB).sections[0].entries[2]
    assert [b.text for b in entry.bullets] == ["1", "2", "3"]


@pytest.mark.parametrize("template", ["cover-letter", "cover-letter-email", "thank-you", "follow-up"])
def test_letters_carry_the_location_under_the_name(template: str) -> None:
    doc = build(template, FULL, interviewer="I", interview_date="d", applied_date="d", **JOB)
    assert doc.intro == (Line("London", PID),)


def test_write_letter_picks_the_best_positions_and_skills() -> None:
    profile = Profile(
        name="Ada",
        positions=(
            PositionView("Cook", "Diner", achievements=("Fried eggs", "Baked pies", "Plated food")),
            PositionView("Engineer", "Acme", achievements=("Built Python tools", "Wrote docs"), skills=("Python",)),
            PositionView("Pilot", "Air", achievements=("Flew planes",), skills=("Navigation",)),
        ),
        skills=("Python", "Go", "A", "B", "C", "D", "E"),
    )
    job = "python engineer with go a b c d e"
    assert write_letter(profile, job) == "\n".join([
        "Dear Hiring Team,", "", "I am a Engineer at Acme, and I am applying for this role.", "",
        "- Built Python tools", "- Wrote docs", "- Fried eggs",
        "", "My experience includes Python, Go, A, B, C, which is relevant to this role.",
        "", "Thank you for your consideration.", "", "Ada"])


def test_write_letter_without_positions_or_skills() -> None:
    assert write_letter(Profile(name="Bob"), "x") == "\n".join([
        "Dear Hiring Team,", "", "I am applying for this role.", "", "Thank you for your consideration.", "", "Bob"])


def test_write_letter_variants_without_organization_or_bullets() -> None:
    lone = Profile(name="Cy", positions=(PositionView("Chef", ""),))
    assert write_letter(lone, "x") == "\n".join([
        "Dear Hiring Team,", "", "I am a Chef, and I am applying for this role.",
        "", "Thank you for your consideration.", "", "Cy"])
    two = Profile(name="D", positions=(PositionView("A", "O"), PositionView("B", "P", achievements=("Did B",))))
    assert "- Did B" in write_letter(two, "a b")
    one = Profile(name="E", positions=(PositionView("A", "O", achievements=("1", "2", "3")),))
    assert write_letter(one, "a").count("\n- ") == 2
