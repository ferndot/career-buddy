"""Append-only JSON Lines event log. One event per line, tagged by `type`."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

from career_buddy.domain.events import (
    DuplicateDismissed,
    Event,
    FactDeleted,
    FactRevised,
    FactsImported,
    FactsMerged,
    LinkAdded,
    LinkRemoved,
    SourceRegistered,
    SourceRemoved,
)
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind

log = logging.getLogger(__name__)


def _encode(event: Event) -> dict[str, object]:
    match event:
        case FactsImported(batch, source_key):
            return {**({"source_key": source_key} if source_key else {}),
                "type": "FactsImported",
                "facts": [
                    {"id": f.id, "kind": f.kind.value, "title": f.title, "attributes": f.attributes, "source": f.source}
                    for f in batch.facts
                ],
                "links": [{"source_id": l.source_id, "target_id": l.target_id, "kind": l.kind.value} for l in batch.links],
            }
        case FactRevised():
            return {"type": "FactRevised", "fact_id": event.fact_id, "title": event.title,
                    "attributes": event.attributes, "at": event.at}
        case FactsMerged():
            return {"type": "FactsMerged", "alias_id": event.alias_id, "canonical_id": event.canonical_id,
                    "at": event.at, "undo": event.undo, "auto": event.auto}
        case DuplicateDismissed():
            return {"type": "DuplicateDismissed", "a_id": event.a_id, "b_id": event.b_id, "at": event.at}
        case SourceRegistered():
            return {"type": "SourceRegistered", "source": event.source, "source_key": event.source_key, "at": event.at}
        case SourceRemoved():
            return {"type": "SourceRemoved", "source": event.source, "at": event.at}
        case FactDeleted():
            return {"type": "FactDeleted", "fact_id": event.fact_id, "at": event.at}
        case LinkAdded() | LinkRemoved():
            return {"type": type(event).__name__, "source_id": event.source_id, "target_id": event.target_id,
                    "kind": event.kind, "at": event.at}


def _decode(record: dict[str, object]) -> Event | None:
    match record["type"]:
        case "FactsImported":
            facts = tuple(
                Fact(f["id"], FactKind(f["kind"]), f["title"], f["attributes"], f["source"]) for f in record["facts"]
            )
            links = tuple(Link(l["source_id"], l["target_id"], LinkKind(l["kind"])) for l in record["links"])
            return FactsImported(FactBatch(facts, links), record.get("source_key", ""))
        case "FactRevised":
            return FactRevised(record["fact_id"], record["title"], record["attributes"], record.get("at", ""))
        case "FactsMerged":
            return FactsMerged(record["alias_id"], record["canonical_id"], record.get("undo", False), record.get("at", ""), record.get("auto", False))
        case "DuplicateDismissed":
            return DuplicateDismissed(record["a_id"], record["b_id"], record.get("at", ""))
        case "SourceRegistered":
            return SourceRegistered(record["source"], record["source_key"], record.get("at", ""))
        case "SourceRemoved":
            return SourceRemoved(record["source"], record.get("at", ""))
        case "FactDeleted":
            return FactDeleted(record["fact_id"], record.get("at", ""))
        case "LinkAdded" | "LinkRemoved":
            cls = LinkAdded if record["type"] == "LinkAdded" else LinkRemoved
            return cls(record["source_id"], record["target_id"], record["kind"], record.get("at", ""))
    log.warning("Skipping unknown event type %r", record["type"])
    return None


class JsonlEventLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_encode(event), ensure_ascii=False) + "\n")

    def replay(self) -> Iterable[Event]:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip() and (event := _decode(json.loads(line))) is not None:
                yield event
