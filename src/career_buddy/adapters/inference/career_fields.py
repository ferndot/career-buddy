"""What the career chat tells its model about the fields of each kind, generated from the career schema (the extraction schema's single source of truth)."""

from __future__ import annotations

from redstring.extraction.domains import load_schema_from_file

from career_buddy.adapters.inference.redstring_extractor import CAREER_SCHEMA

# Fields the user writes by hand that extraction never fills, so the schema does not list them.
MANUAL_FIELDS = {"Person": ["summary"], "Position": ["organization"], "Education": ["school"]}
# Where a kind's own text is its title rather than an attribute.
TITLES = {"Position": "its title", "Achievement": "its text", "Skill": "its name", "Education": "the degree"}


def schema_fields() -> dict[str, dict[str, str]]:
    """Each kind's schema properties as {name: type}."""
    schema = load_schema_from_file(CAREER_SCHEMA)
    return {e.id.capitalize(): {p.name: str(getattr(p.type, "value", p.type)) for p in (e.properties or [])} for e in schema.entity_types}


def edit_fields() -> dict[str, list[str]]:
    """The attributes edit_fact may change, per kind: the schema's, then the hand-written ones."""
    fields = schema_fields()
    return {kind: [*fields.get(kind, {}), *MANUAL_FIELDS.get(kind, [])] for kind in sorted({*fields, *MANUAL_FIELDS}) if kind != "Organization"}


def field_guide() -> str:
    """One short line per kind, for the prompt and the edit_fact description."""
    fields = schema_fields()
    lines = []
    for kind, names in edit_fields().items():
        shown = [f"{n} (a whole number of 0 or more, never text)" if fields.get(kind, {}).get(n) == "number" else n for n in names]
        title = f"title is {TITLES[kind]}; " if kind in TITLES else ""
        lines.append(f"{kind}: {title}fields {', '.join(shown) or 'none'}")
    return "; ".join(lines)
