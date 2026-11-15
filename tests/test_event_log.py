"""The JSONL log round-trips every event type and still reads a v1 (FactsImported-only) log."""

import json
import shutil
from pathlib import Path

from career_graph.adapters.storage.jsonl_event_log import JsonlEventLog
from career_graph.domain.events import FactRevised, FactsImported, FactsMerged
from career_graph.domain.model import Fact, FactBatch, FactKind, Link, LinkKind

V1_LOG = Path(__file__).parent / "fixtures" / "events-v1.jsonl"

EVENTS = [
    FactsImported(FactBatch((Fact("a", FactKind.SKILL, "Python", {"x": "y"}, "src"),), (Link("p", "a", LinkKind.HAS_SKILL),))),
    FactRevised("a", "Python 3", {"hidden": "true"}, "2026-11-14T10:00:00+00:00"),
    FactsMerged("b", "a", False, "2026-11-14T10:01:00+00:00"),
    FactsMerged("b", "a", True, "2026-11-14T10:02:00+00:00"),
    FactsImported(FactBatch((Fact("b", FactKind.SKILL, "Rust"),)), "sources/abc.pdf"),
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


def test_v1_log_replays(tmp_path: Path) -> None:
    shutil.copy(V1_LOG, tmp_path / "events.jsonl")
    events = list(JsonlEventLog(tmp_path / "events.jsonl").replay())
    assert len(events) == 2 and all(isinstance(e, FactsImported) for e in events)
