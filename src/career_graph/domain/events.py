"""Domain events. The event log is the source of truth; the graph is a projection of it."""

from __future__ import annotations

from dataclasses import dataclass, field

from career_graph.domain.model import FactBatch


@dataclass(frozen=True)
class FactsImported:
    batch: FactBatch
    source_key: str = ""  # object-store key of the original upload, when one was kept


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


@dataclass(frozen=True)
class DuplicateDismissed:
    """The user said these two facts are not the same, so the pair is not proposed again. Order does not matter."""

    a_id: str
    b_id: str
    at: str = ""


Event = FactsImported | FactRevised | FactsMerged | DuplicateDismissed
