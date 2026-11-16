"""Template cover letter: picks the strongest matching positions and achievements for the job text."""

from __future__ import annotations

from career_buddy.domain.profile import Profile, rank_for_job

# shortcut: v1 letter text kept as a pure function until the cover-letter template (Phase 5) replaces it.


def write_letter(profile: Profile, job_text: str) -> str:
    positions, skills = rank_for_job(profile, job_text)
    lines = ["Dear Hiring Team,", ""]
    if positions:
        top = positions[0]
        lead = f"I am a {top.title} at {top.organization}" if top.organization else f"I am a {top.title}"
        lines.append(f"{lead}, and I am applying for this role.")
        achievements = list(top.achievements[:2])
        if len(positions) > 1 and positions[1].achievements:
            achievements.append(positions[1].achievements[0])
        if achievements:
            lines.append("")
            lines += [f"- {a}" for a in achievements]
    else:
        lines.append("I am applying for this role.")
    if skills:
        lines += ["", f"My experience includes {', '.join(skills[:5])}, which is relevant to this role."]
    lines += ["", "Thank you for your consideration.", "", profile.name]
    return "\n".join(lines)
