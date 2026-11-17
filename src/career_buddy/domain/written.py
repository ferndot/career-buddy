"""The document a writer writes: sections of items, each text citing the facts it rests on. Pure.

The writer is told the template's section keys and answers `{"sections": [{"key", "items": [...]}]}`; this module is the schema
of that answer and the rules that make it safe to print:

- `summary`: one item `{text, fact_ids}`. `skills`: items `{text, fact_ids}` naming skills. `education`: items `{text, fact_ids}`,
  each citing an education entry. `body` (a letter): paragraph items `{text, fact_ids}`.
- `experience`: one item per position `{position_id, also, bullets: [{text, fact_ids}]}`. The writer chooses how many bullets a
  position gets and how they read. A bullet rests on at least one achievement of its position, which it cites first. When
  several positions at one company are condensed, one item names the newest as `position_id` and the older ones as `also`: it
  prints one heading line per position (each its own title and dates) and then the item's one combined set of bullets, which may
  cite the achievements of any of them.

Every text has a slot id, the key of the user's own wording and of the saved layout (domain/slots.py): `summary`, `skills`,
`edu:<first cited education id>`, `para:<n>` and, for a bullet, `bullet:<first cited achievement id>`; a repeat gets `#2`, `#3`.
So a bullet keeps its id when the writer rewords it, and a person's edit survives a regenerate while the bullet still rests on
the same fact. A person's pinned slot is never lost: the writer's text for it is blanked, and a slot the writer left out is added.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from career_buddy.domain.document import Document, Entry, Line, Origin
from career_buddy.domain.document import Section as PrintedSection
from career_buddy.domain.generation import Brief, BriefFact
from career_buddy.domain.templates import TemplateSpec

LETTER = "body"  # the section key of a letter's paragraphs
MAX_PARAGRAPHS = 6


class _Written(BaseModel):
    model_config = ConfigDict(frozen=True)


class Bullet(_Written):
    text: str
    fact_ids: tuple[str, ...] = ()
    slot: SkipJsonSchema[str] = ""  # numbered by `numbered`, never written by the model


class Item(_Written):
    text: str = ""
    fact_ids: tuple[str, ...] = ()
    position_id: str = ""  # experience: the position this item is about (the newest, when it condenses several)
    also: tuple[str, ...] = ()  # experience: older positions condensed under it, same company
    bullets: tuple[Bullet, ...] = ()  # experience: its bullets
    slot: SkipJsonSchema[str] = ""


class Section(_Written):
    key: str
    items: tuple[Item, ...] = ()


class WrittenDocument(_Written):
    sections: tuple[Section, ...]


# the text of one node, with its slot and the facts it cites: what grounding checks and what an edit changes
Edit = Callable[[str, str, tuple[str, ...]], tuple[str, tuple[str, ...]] | None]  # (slot, text, fact ids) -> new (text, ids), or None to drop


def numbered(doc: WrittenDocument) -> WrittenDocument:
    """The document with every slot id assigned in reading order, whatever it held before."""
    seen: Counter[str] = Counter()

    def slot(base: str) -> str:
        seen[base] += 1
        return base if seen[base] == 1 else f"{base}#{seen[base]}"

    sections = []
    for s in doc.sections:
        items = []
        for n, it in enumerate(s.items, 1):
            first = it.fact_ids[0] if it.fact_ids else str(n)
            if s.key == "experience":
                items.append(it.model_copy(update={"bullets": tuple(b.model_copy(update={"slot": slot(f"bullet:{b.fact_ids[0] if b.fact_ids else n}")}) for b in it.bullets)}))
                continue
            base = {"summary": "summary", "skills": "skills", "education": f"edu:{first}", LETTER: f"para:{n}"}.get(s.key, f"{s.key}:{n}")
            items.append(it.model_copy(update={"slot": slot(base)}))
        sections.append(s.model_copy(update={"items": tuple(items)}))
    return WrittenDocument(sections=tuple(sections))


def nodes(doc: WrittenDocument) -> list[tuple[str, str, tuple[str, ...]]]:
    """Every text of the document as (slot, text, fact ids), in reading order."""
    out = []
    for s in numbered(doc).sections:
        for it in s.items:
            out += [(b.slot, b.text, b.fact_ids) for b in it.bullets] if s.key == "experience" else [(it.slot, it.text, it.fact_ids)]
    return out


def texts(doc: WrittenDocument) -> dict[str, str]:
    """The slot -> text of every node that has text."""
    return {slot: text for slot, text, _ in nodes(doc) if text}


def mapped(doc: WrittenDocument, edit: Edit) -> WrittenDocument:
    """The document with `edit` applied to every text. A bullet dropped by `edit` leaves its position without it, and a position
    left with no bullet goes; any other dropped item goes."""
    sections = []
    for s in numbered(doc).sections:
        items = []
        for it in s.items:
            if s.key == "experience":
                done = [(b, edit(b.slot, b.text, b.fact_ids)) for b in it.bullets]
                bullets = tuple(Bullet(text=r[0], fact_ids=r[1]) for b, r in done if r)
                if bullets:
                    items.append(it.model_copy(update={"bullets": bullets}))
            elif r := edit(it.slot, it.text, it.fact_ids):
                items.append(it.model_copy(update={"text": r[0], "fact_ids": r[1]}))
        sections.append(s.model_copy(update={"items": tuple(items)}))
    return numbered(WrittenDocument(sections=tuple(s for s in sections if s.items)))


def _ids(brief: Brief, ids: tuple[str, ...]) -> tuple[str, ...]:
    known = {f.id for f in brief.facts}
    return tuple(dict.fromkeys(i for i in ids if i in known))


def _experience(brief: Brief, section: Section, facts: Mapping[str, BriefFact]) -> list[Item]:
    """One item per position or, where the writer condensed several under one (`also`), per group, in the brief's order. A group's
    positions are sorted newest first and a position belongs to one item only. Bullets: those resting on an achievement of the item's
    positions, up to the cap per position plus one for each further position of a group."""
    order = {f.id: n for n, f in enumerate(f for f in brief.facts if f.kind == "position")}
    members: dict[str, list[str]] = {}  # the item's lead position -> its positions
    claimed: dict[str, str] = {}  # position -> the lead of the item it belongs to
    bullets: dict[str, list[Bullet]] = {}
    for item in section.items:
        ids = sorted({p for p in (item.position_id, *item.also) if p in order}, key=order.__getitem__)
        if not ids or claimed.get(ids[0], ids[0]) != ids[0]:
            continue
        lead = ids[0]
        group = members.setdefault(lead, [])
        group += [p for p in ids if claimed.setdefault(p, lead) == lead and p not in group]
        for b in item.bullets:
            cited = _ids(brief, b.fact_ids)
            own = tuple(i for i in cited if facts[i].kind == "achievement" and facts[i].position_id in group)
            if own and b.text.strip():
                bullets.setdefault(lead, []).append(Bullet(text=b.text.strip(), fact_ids=(*own, *(i for i in cited if i not in own))))
    return [Item(position_id=lead, also=tuple(sorted(members[lead], key=order.__getitem__)[1:]),
                 bullets=tuple(bullets[lead][: brief.caps.bullets + len(members[lead]) - 1])) for lead in sorted(bullets, key=order.__getitem__)]


def _items(brief: Brief, section: Section, facts: Mapping[str, BriefFact]) -> list[Item]:
    items = [Item(text=i.text.strip(), fact_ids=_ids(brief, i.fact_ids)) for i in section.items if i.text.strip()]
    if section.key == "summary":
        return items[:1]
    if section.key == LETTER:
        return items[:MAX_PARAGRAPHS]
    if section.key == "education":  # the slot is the education entry it cites, which comes first; an item citing none goes
        edu = [(i, [x for x in i.fact_ids if facts[x].kind == "education"]) for i in items]
        return [Item(text=i.text, fact_ids=(*e, *(x for x in i.fact_ids if x not in e))) for i, e in edu if e]
    if section.key == "skills":  # at most the cap of distinct skills in all: the line that would pass it, and every later one, goes
        used: set[str] = set()
        kept = []
        for i in items:
            used |= {x for x in i.fact_ids if facts[x].kind == "skill"}
            if len(used) > brief.caps.skills:
                break
            kept.append(i)
        return kept
    return []


def validated(brief: Brief, doc: WrittenDocument) -> WrittenDocument:
    """What the writer wrote, made fit to check and print: the brief's sections only, in the template's order, a section's first
    answer only; cited ids the brief lacks dropped; empty and over-cap items dropped (bullets per position, skills, paragraphs);
    no bullet without an achievement of its position (or of a position its item condenses) behind it. Then the person's pinned slots are put back (see `pinned`)."""
    facts = {f.id: f for f in brief.facts}
    first = {s.key: s for s in reversed(doc.sections)}
    kept = {key: (_experience if key == "experience" else _items)(brief, first[key], facts) for key in brief.sections if key in first}
    return pinned(brief, numbered(WrittenDocument(sections=tuple(Section(key=k, items=tuple(i)) for k in brief.sections if (i := kept.get(k))))))


def pinned(brief: Brief, doc: WrittenDocument) -> WrittenDocument:
    """The person's own slots stay: the writer's text for one is blanked (their words take its place when the document is read), and
    a pinned slot the writer left out is added to its section, a bullet to its position."""
    present = {slot for slot, _, _ in nodes(doc)}
    doc = mapped(doc, lambda slot, text, ids: ("", ids) if slot in brief.pinned else (text, ids)) if brief.pinned & present else doc
    facts = {f.id: f for f in brief.facts}
    by_key = {s.key: list(s.items) for s in doc.sections}
    for slot in sorted(brief.pinned - present):
        base = slot.split("#")[0]
        key, _, rest = base.partition(":")
        if key == "summary" and "summary" in brief.sections:
            by_key.setdefault("summary", []).append(Item())
        elif key == "skills" and "skills" in brief.sections:
            by_key.setdefault("skills", []).append(Item())
        elif key == "edu" and "education" in brief.sections and facts.get(rest) and facts[rest].kind == "education":
            by_key.setdefault("education", []).append(Item(fact_ids=(rest,)))
        elif key == "para" and rest.isdigit() and LETTER in brief.sections and int(rest) <= MAX_PARAGRAPHS:
            paragraphs = by_key.setdefault(LETTER, [])
            paragraphs += [Item()] * (int(rest) - len(paragraphs))
        elif key == "bullet" and "experience" in brief.sections and facts.get(rest) and facts[rest].kind == "achievement":
            items = by_key.setdefault("experience", [])
            at = next((n for n, i in enumerate(items) if facts[rest].position_id in (i.position_id, *i.also)), None)
            if at is None:
                items.append(Item(position_id=facts[rest].position_id))
                at = len(items) - 1
            items[at] = items[at].model_copy(update={"bullets": (*items[at].bullets, Bullet(text="", fact_ids=(rest,)))})
    return numbered(WrittenDocument(sections=tuple(Section(key=k, items=tuple(by_key[k])) for k in brief.sections if by_key.get(k))))


def to_document(base: Document, spec: TemplateSpec, doc: WrittenDocument, headings: Mapping[str, str]) -> Document:
    """`base` (the name, contact lines and layout of the template) with the written sections in place of its own. Each text line carries
    its slot id and the facts it cites, so a saved layout can find it again. `headings` are the position headings, by position id.
    The text of a position's heading is the facts', never the writer's."""
    labels = dict(spec.sections)
    allowed = {LETTER} if spec.kind == "letter" else set(labels)
    person = base.name.source_fact_id
    printed: list[PrintedSection] = []
    for s in numbered(doc).sections:
        if s.key not in allowed:  # a client's sections are not trusted
            continue
        if s.key == LETTER:
            printed.append(PrintedSection("", tuple(Entry(paragraph=Line(i.text, None, Origin.BOILERPLATE, slot=i.slot)) for i in s.items)))
        elif s.key == "experience":
            entries: list[Entry] = []
            for i in s.items:  # a condensed item: a heading line for each position, its bullets after the last
                held = [p for p in (i.position_id, *i.also) if p in headings]
                lines = tuple(Line(b.text, b.fact_ids[0], field="title", cites=b.fact_ids, slot=b.slot) for b in i.bullets if b.fact_ids)
                entries += [Entry(heading=Line(headings[p], p, field="heading"), bullets=lines if n == len(held) - 1 else ()) for n, p in enumerate(held)]
            printed.append(PrintedSection(labels[s.key], tuple(entries)))
        elif s.key == "education":
            printed.append(PrintedSection(labels[s.key], (Entry(bullets=tuple(Line(i.text, i.fact_ids[0], field="label", cites=i.fact_ids, slot=i.slot) for i in s.items if i.fact_ids)),)))
        else:  # summary, skills
            printed.append(PrintedSection(labels[s.key], tuple(Entry(paragraph=Line(i.text, person, field=s.key, cites=i.fact_ids, slot=i.slot)) for i in s.items)))
    if spec.kind == "letter" and not printed:
        printed = [PrintedSection("", ())]
    return replace(base, sections=tuple(printed))


def blank_letter(slots: Mapping[str, str]) -> WrittenDocument | None:
    """A letter the person wrote themselves: a body of empty paragraphs up to the highest `para:<n>` they gave, whose words come
    from their overrides. None when they gave no paragraph."""
    last = max((int(k[5:]) for k in slots if k.startswith("para:") and k[5:].isdigit()), default=0)
    return WrittenDocument(sections=(Section(key=LETTER, items=(Item(),) * min(last, MAX_PARAGRAPHS)),)) if last else None
