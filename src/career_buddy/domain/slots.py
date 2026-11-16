"""Slots: the text places of a saved document, and how their text is found. Pure.

A saved document keeps only a layout. Each text line is a slot with a stable id. The facts' text is not stored: it is found
when the document is shown or downloaded, in this order:

1. the user's override for the slot (`overrides.json`), their own words;
2. the text a writer generated for it (`generated.json`), unless the facts it was written from have changed since;
3. the current value of the fact the slot is bound to (so edits to the career facts flow into the document);
4. the placeholder, which is the layout's fixed wording (a greeting, a letter's template sentences), empty otherwise.

Slot ids: `name`, `location`, `headline`, `summary`, `skills`, `greeting`, `subject`, `closing`, `signature`,
`heading:<position id>`, `bullet:<achievement id>`, `edu:<education id>` and, for fixed body lines and a letter's
paragraphs, `para:<n>`. A second slot that would reuse an id gets `#2`, `#3`, and so on.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Literal

from career_buddy.domain.document import Document, Entry, Line, Origin, Section
from career_buddy.domain.profile import Profile
from career_buddy.domain.templates import position_heading

Role = Literal["name", "intro", "heading", "paragraph", "bullet"]
Lookup = Mapping[tuple[str, str], str]  # (fact id, field) -> the fact's current text

# Fields whose text comes from facts. Any other field (or none) is fixed wording and never resolves from a fact.
FACT_FIELDS = frozenset({"title", "location", "headline", "summary", "skills", "heading", "label"})
_NAMED = frozenset({"location", "headline", "summary", "skills", "greeting", "closing", "subject"})
PARA = "para:"


@dataclass(frozen=True)
class Written:
    """Text a writer wrote for a slot. `source` is what the slot's facts said then, kept for a bullet (the writer reworded one
    fact) and for the skills list: when the facts say something else now, the text is stale and the facts show instead.

    shortcut: a summary or a paragraph rests on many facts and has no source, so it stays until the user regenerates or edits it."""

    text: str
    source: str = ""


@dataclass(frozen=True)
class Slot:
    id: str
    fact_ids: tuple[str, ...] = ()
    field: str = ""
    placeholder: str = ""  # the layout's text for the slot


def slot_for(role: Role, line: Line, taken: set[str]) -> Slot:
    """The slot of one line of a layout. `taken` holds the ids given so far and gains this one."""
    fid, field = line.source_fact_id or "", line.field
    bound = field in FACT_FIELDS and bool(fid or line.cites)
    if bound and field == "title":
        base = {"name": "name", "paragraph": "signature"}.get(role, f"bullet:{fid}")
    elif bound and field == "heading":
        base = f"heading:{fid}"
    elif bound and field == "label":
        base = f"edu:{fid}"
    elif field in _NAMED:
        base = field
    elif role == "name":
        base = "name"
    elif role == "intro":
        base = f"intro:{sum(k.startswith('intro:') for k in taken) + 1}"
    else:
        base = f"{PARA}{sum(k.startswith(PARA) for k in taken) + 1}"
    slot_id, n = base, 1
    while slot_id in taken:
        n += 1
        slot_id = f"{base}#{n}"
    taken.add(slot_id)
    if not bound:
        return Slot(slot_id, (), "", line.text)
    return Slot(slot_id, line.cites or (fid,), field, "")


def source_of(slot: Slot, lookup: Lookup) -> str:
    """What the facts bound to a slot say now."""
    return ", ".join(text for fid in slot.fact_ids if (text := lookup.get((fid, slot.field), "")))


def written_for(slots: Iterable[Slot], texts: Mapping[str, str], lookup: Lookup) -> dict[str, Written]:
    """The generated texts that name a slot of the layout, each with the source it was written from where that matters."""
    by_id = {slot.id: slot for slot in slots}
    return {k: Written(text.strip(), source_of(by_id[k], lookup) if k.startswith("bullet:") or k == "skills" else "")
            for k, text in texts.items() if k in by_id and text.strip()}


def resolve(slots: Iterable[Slot], overrides: Mapping[str, str], lookup: Lookup, generated: Mapping[str, Written] = {}) -> dict[str, str]:
    """The text of every slot: override, then fresh generated text, then the bound facts' current text, then the placeholder."""
    out: dict[str, str] = {}
    for slot in slots:
        current, made = source_of(slot, lookup), generated.get(slot.id)
        if own := overrides.get(slot.id, "").strip():
            out[slot.id] = own
        elif made and made.text and (not made.source or made.source == current):
            out[slot.id] = made.text
        else:
            out[slot.id] = current or slot.placeholder
    return out


def fact_texts(profile: Profile) -> dict[tuple[str, str], str]:
    """What every fact in the profile says now, by (fact id, field). Hidden facts are absent: their slots fall back."""
    out: dict[tuple[str, str], str] = {}
    if profile.id:
        out[(profile.id, "title")] = profile.name
        out |= {(profile.id, k): profile.attributes[k] for k in ("location", "headline", "summary") if profile.attributes.get(k)}
    out |= {(sid, "skills"): title for sid, title in zip(profile.skill_ids, profile.skills)}
    for pos in profile.positions:
        out[(pos.id, "heading")] = position_heading(pos)
        out |= {(aid, "title"): text for aid, text in zip(pos.achievement_ids, pos.achievements)}
    out |= {(e.id, "label"): e.label for e in profile.education if e.id}
    return out


def layout_overrides(given: Mapping[str, str], slots: Iterable[str]) -> dict[str, str]:
    """The overrides a save request carries, as slot ids. A bare fact id means that fact's bullet. Others are dropped."""
    ids = set(slots)
    out: dict[str, str] = {}
    for key, text in given.items():
        slot = next((k for k in (key, f"bullet:{key}", f"heading:{key}", f"edu:{key}") if k in ids), None)
        if slot and text.strip():
            out[slot] = text.strip()
    return out


def with_paragraphs(doc: Document, count: int) -> Document:
    """A letter whose body is `count` empty paragraph slots in place of its template sentences, bullets and sign-off text.

    The greeting, subject, closing and the name under it stay. The paragraphs get their words from overrides."""
    if not doc.sections:
        return doc

    def field(entry: Entry) -> str:
        return entry.paragraph.field if entry.paragraph and not entry.bullets else ""

    entries = doc.sections[0].entries
    head = [e for e in entries if field(e) in ("greeting", "subject")]
    tail = [e for e in entries if field(e) in ("closing", "title")]  # the sign-off and the name under it
    body = [Entry(paragraph=Line("", None, Origin.BOILERPLATE)) for _ in range(count)]
    return replace(doc, sections=(Section(doc.sections[0].title, (*head, *body, *tail)), *doc.sections[1:]))


def paragraph_indexes(keys: Iterable[str]) -> list[int]:
    return sorted({int(k[len(PARA):]) for k in keys if k.startswith(PARA) and k[len(PARA):].isdigit()})
