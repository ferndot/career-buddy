"""Domain events. The event log is the source of truth; the graph is a projection of it."""

from __future__ import annotations

from dataclasses import dataclass, field

from career_buddy.domain.model import FactBatch


@dataclass(frozen=True)
class FactsImported:
    batch: FactBatch
    source_key: str = ""  # object-store key of the original upload, when one was kept


@dataclass(frozen=True)
class SourceRegistered:
    """A source was imported and its original stored under `source_key`, whether or not extraction has succeeded yet."""

    source: str
    source_key: str
    at: str = ""


@dataclass(frozen=True)
class FactRevised:
    """Full replacement of a fact's title and attributes. Hide = attributes["hidden"] == "true"."""

    fact_id: str
    title: str
    attributes: dict[str, str] = field(default_factory=dict)
    at: str = ""


@dataclass(frozen=True)
class FactsMerged:
    """The alias is shown as the canonical fact. `undo` reverses an earlier merge of the same pair."""

    alias_id: str
    canonical_id: str
    undo: bool = False
    at: str = ""
    auto: bool = False  # the import merged them (a near-certain duplicate), not the user


@dataclass(frozen=True)
class DuplicateDismissed:
    """The user said these two facts are not the same, so the pair is not proposed again. Order does not matter."""

    a_id: str
    b_id: str
    at: str = ""


@dataclass(frozen=True)
class SourceRemoved:
    """The user removed a source. Its facts are hidden, except any fact another source also states."""

    source: str
    at: str = ""


@dataclass(frozen=True)
class FactDeleted:
    """The user deleted a fact for good. A position's achievements go with it."""

    fact_id: str
    at: str = ""


@dataclass(frozen=True)
class LinkAdded:
    """The user linked two facts. Wins over an earlier LinkRemoved of the same link."""

    source_id: str
    target_id: str
    kind: str
    at: str = ""


@dataclass(frozen=True)
class LinkRemoved:
    """The user unlinked two facts. A re-import of the link does not bring it back."""

    source_id: str
    target_id: str
    kind: str
    at: str = ""


Event = FactsImported | SourceRegistered | FactRevised | FactsMerged | DuplicateDismissed | SourceRemoved | FactDeleted | LinkAdded | LinkRemoved
