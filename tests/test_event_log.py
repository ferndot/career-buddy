"""The JSONL log round-trips every event type."""

import json
from pathlib import Path

from career_buddy.adapters.storage.jsonl_event_log import JsonlEventLog
from career_buddy.domain.events import FactDeleted, FactRevised, FactsImported, FactsMerged, LinkAdded, LinkRemoved, SourceRegistered
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind

EVENTS = [
    FactsImported(FactBatch((Fact("a", FactKind.SKILL, "Python", {"x": "y"}, "src"),), (Link("p", "a", LinkKind.HAS_SKILL),))),
    FactRevised("a", "Python 3", {"hidden": "true"}, "2026-11-14T10:00:00+00:00"),
    FactsMerged("b", "a", False, "2026-11-14T10:01:00+00:00"),
    FactsMerged("b", "a", True, "2026-11-14T10:02:00+00:00"),
    FactsImported(FactBatch((Fact("b", FactKind.SKILL, "Rust"),)), "sources/abc.pdf"),
    FactDeleted("b", "2026-11-14T10:03:00+00:00"),
    LinkAdded("p", "o", "AT", "2026-11-14T10:04:00+00:00"),
    LinkRemoved("p", "o", "AT", "2026-11-14T10:05:00+00:00"),
    SourceRegistered("cv.pdf", "sources/abc.pdf", "2026-11-14T10:06:00+00:00"),
]


def test_every_event_type_round_trips(tmp_path: Path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    for event in EVENTS:
        log.append(event)
    assert list(JsonlEventLog(tmp_path / "events.jsonl").replay()) == EVENTS


def test_unknown_event_types_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    log.append(EVENTS[1])
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "FromTheFuture"}) + "\n")
    log.append(EVENTS[2])
    assert list(log.replay()) == [EVENTS[1], EVENTS[2]]
