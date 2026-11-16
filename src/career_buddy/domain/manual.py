"""Facts added by hand: where each kind may attach, and the links that make them show up."""

from __future__ import annotations

from career_buddy.domain.dates import checked
from career_buddy.domain.model import Fact, FactBatch, FactKind, InvalidFact, Link, LinkKind, fact_id

PARENT_LINKS = {
    (FactKind.POSITION, FactKind.PERSON): LinkKind.HAS_POSITION,
    (FactKind.EDUCATION, FactKind.PERSON): LinkKind.HAS_EDUCATION,
    (FactKind.SKILL, FactKind.PERSON): LinkKind.HAS_SKILL,
    (FactKind.ACHIEVEMENT, FactKind.POSITION): LinkKind.ACHIEVED,
}


def manual_fact(kind: FactKind, title: str, parent: Fact | None, attributes: dict[str, str]) -> FactBatch:
    """The batch that adds one fact under `parent`. The new fact comes first. Raises InvalidFact."""
    title = title.strip()
    link_kind = PARENT_LINKS.get((kind, parent.kind)) if parent else None
    if not title or link_kind is None:
        raise InvalidFact("A title and a valid parent are required" if parent else f"A {kind} needs a parent")
    attrs = checked({k: v.strip() for k, v in attributes.items() if v.strip()})
    employer = ""
    if kind in (FactKind.POSITION, FactKind.EDUCATION):
        employer = attrs.pop("organization", "") if kind == FactKind.POSITION else attrs.get("school", "")
    scope = parent.id if kind == FactKind.ACHIEVEMENT else employer
    fact = Fact(fact_id(kind, title, scope), kind, title, attrs, "manual")
    facts, links = [fact], [Link(parent.id, fact.id, link_kind)]
    if employer:
        # Same ids as the importers, so "Acme Corp" typed by hand joins the Acme Corp already there.
        org = Fact(fact_id(FactKind.ORGANIZATION, employer), FactKind.ORGANIZATION, employer, {}, "manual")
        facts.append(org)
        links.append(Link(fact.id, org.id, LinkKind.AT if kind == FactKind.POSITION else LinkKind.ATTENDED))
    return FactBatch(tuple(facts), tuple(links))
