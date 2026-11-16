"""Sources are additive; near-certain duplicates merge on import and the rest are suggested; edits survive a reindex, an inert merge shows its alias, a dismissal survives merges."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st

from career_buddy.adapters.graph.redstring_graph import RedstringFactGraph
from career_buddy.application.projector import Projector
from career_buddy.domain.dedup import AUTO_MERGE_THRESHOLD, auto_merges, canonical_of
from career_buddy.domain.events import DuplicateDismissed, FactRevised, FactsImported, FactsMerged, SourceRemoved
from career_buddy.domain.model import Fact, FactBatch, FactKind
from career_buddy.web.app import create_app

fact_titles = st.text(alphabet="abcdef ", min_size=1, max_size=8)


@given(fact_titles, fact_titles, st.sets(st.sampled_from(["a", "b"])))
def test_the_kept_fact_is_one_of_the_two_whichever_way_round_and_a_lone_touched_fact_wins(ta: str, tb: str, touched: set[str]) -> None:
    a, b = Fact("a", FactKind.ORGANIZATION, ta), Fact("b", FactKind.ORGANIZATION, tb)
    kept = canonical_of(a, b, touched)
    assert kept in ("a", "b") and kept == canonical_of(b, a, touched)
    if len(touched) == 1:
        assert kept == next(iter(touched))
    elif len(ta) != len(tb):
        assert kept == ("a" if len(ta) > len(tb) else "b")


scores = st.floats(0, 1) | st.sampled_from([AUTO_MERGE_THRESHOLD, 0.0, 1.0])


@given(scores, st.sets(st.sampled_from(["a", "b"])), st.booleans(), st.booleans(), st.booleans())
def test_a_pair_is_merged_automatically_only_at_or_above_the_bar_and_when_neither_is_touched_hidden_or_dismissed(
    score: float, touched: set[str], hidden: bool, dismissed: bool, same_kind: bool
) -> None:
    a = Fact("a", FactKind.ORGANIZATION, "Acme", {"hidden": "true"} if hidden else {})
    b = Fact("b", FactKind.ORGANIZATION if same_kind else FactKind.SKILL, "Acme Corp")
    merged = auto_merges(FactBatch((a, b)), [("a", "b", score)], touched, [frozenset("ab")] if dismissed else [])
    if score >= AUTO_MERGE_THRESHOLD and not (touched or hidden or dismissed) and same_kind:
        assert merged == [("a", "b")]  # the fuller title is kept
    else:
        assert merged == []


@given(st.lists(st.tuples(st.sampled_from("abcd"), st.sampled_from("abcd"), scores).filter(lambda c: c[0] < c[1]), max_size=6),
       st.sets(st.sampled_from("abcd")))
def test_no_touched_fact_is_ever_merged_automatically_and_no_fact_is_merged_twice(candidates, touched) -> None:
    batch = FactBatch(tuple(Fact(i, FactKind.ORGANIZATION, i * 3) for i in "abcd"))
    merged = auto_merges(batch, candidates, touched)
    used = [i for pair in merged for i in pair]
    assert len(used) == len(set(used)) and not set(used) & touched
    assert all(any(c[:2] in ((x, y), (y, x)) and c[2] >= AUTO_MERGE_THRESHOLD for c in candidates) for x, y in merged)


def org(id: str, title: str, source: str) -> Fact:
    return Fact(id, FactKind.ORGANIZATION, title, {}, source)


def run(events, ask=None):
    async def go():
        projector = Projector(RedstringFactGraph())
        for event in events:
            await projector.project(event)
        return await (ask or Projector.snapshot)(projector)

    return asyncio.run(go())


def visible(events) -> set[str]:
    return {f.id for f in run(events).facts}


def test_a_merge_into_a_fact_no_source_states_any_more_shows_the_alias_again() -> None:
    first = FactsImported(FactBatch((org("canon", "Acme Corp", "a.txt"),)))
    second = FactsImported(FactBatch((org("alias", "Acme", "b.txt"),)))
    merge = FactsMerged("alias", "canon")
    assert visible([first, second, merge]) == {"canon"}
    assert visible([first, second, merge, SourceRemoved("a.txt")]) == {"alias"}
    assert visible([first, second, merge, SourceRemoved("a.txt"), FactsImported(first.batch)]) == {"canon"}  # the canonical is back


@given(st.lists(st.sampled_from(["o1", "o2", "o3", "o4"]), unique=True, max_size=4),
       st.lists(st.tuples(st.sampled_from(["o1", "o2", "o3", "o4"]), st.sampled_from(["o1", "o2", "o3", "o4"])), max_size=3),
       st.lists(st.text(alphabet="abc", min_size=1, max_size=3), min_size=4, max_size=4))
def test_after_edits_and_an_additive_reindex_every_visible_edited_fact_is_still_visible(edited, merges, new_titles) -> None:
    import_one = FactsImported(FactBatch(tuple(org(i, f"Org {i}", "a.txt") for i in ("o1", "o2", "o3", "o4"))))
    edits = [FactRevised(i, f"Mine {i}") for i in edited] + [FactsMerged(x, y) for x, y in merges if x != y]
    before = run([import_one, *edits]).facts
    reindexed = FactsImported(FactBatch(tuple(org(i, t, "a.txt") for i, t in zip(("o1", "o2", "o3", "o4"), new_titles, strict=True))))
    after = {f.id: f for f in run([import_one, *edits, reindexed]).facts}
    for fact in before:
        if fact.id in edited:
            assert after[fact.id].title == f"Mine {fact.id}"


def test_a_dismissed_pair_stays_dismissed_after_one_side_is_merged_into_another_fact() -> None:
    events = [FactsImported(FactBatch(tuple(org(i, i, "a.txt") for i in ("x", "y", "z")))), DuplicateDismissed("x", "y"), FactsMerged("y", "z")]
    assert run(events, Projector.dismissed_now) == {frozenset(("x", "z"))}


def client_with(tmp_path: Path):
    return TestClient(create_app(tmp_path))


def test_removing_the_source_of_a_merged_into_organization_brings_the_alias_back(tmp_path: Path) -> None:
    text = "Jane Doe\n\nExperience\nPlatform Lead at {org}, 2020 - 2021\n- Ran the platform team\n"
    with client_with(tmp_path) as client:
        client.post("/api/import/text", json={"text": text.format(org="Acme Corp"), "source": "a.txt"})
        client.post("/api/import/text", json={"text": text.format(org="Acme"), "source": "b.txt"})
        assert [f["title"] for f in client.get("/api/facts", params={"kind": "Organization"}).json()] == ["Acme Corp"]  # merged on import
        client.delete("/api/sources/a.txt")
        assert [f["title"] for f in client.get("/api/facts", params={"kind": "Organization"}).json()] == ["Acme"]


def test_an_import_merges_a_near_identical_duplicate_and_logs_it_but_keeps_a_borderline_pair_as_a_suggestion(tmp_path: Path) -> None:
    text = "Jane Doe\n\nExperience\nPlatform Lead at {org}, 2020 - 2021\n- Ran the platform team\n"
    with client_with(tmp_path) as client:
        titles = lambda: sorted(f["title"] for f in client.get("/api/facts", params={"kind": "Organization"}).json())  # noqa: E731
        client.post("/api/import/text", json={"text": text.format(org="Globex Inc"), "source": "a.txt"})
        client.post("/api/import/text", json={"text": text.format(org="Globex"), "source": "b.txt"})
        assert titles() == ["Globex Inc"] and client.get("/api/duplicates").json() == []
        assert "Merged duplicate 'Globex' into 'Globex Inc'" in [l["message"] for l in client.get("/api/sources/b.txt/log").json()["lines"]]
        client.post("/api/import/text", json={"text": text.format(org="OpenAI"), "source": "c.txt"})
        client.post("/api/import/text", json={"text": text.format(org="OpenAPI"), "source": "d.txt"})
        assert titles() == ["Globex Inc", "OpenAI", "OpenAPI"]
        (borderline,) = [s for s in client.get("/api/duplicates").json() if s["kind"] == "Organization"]
        assert {borderline["a"]["title"], borderline["b"]["title"]} == {"OpenAI", "OpenAPI"} and 0.9 <= borderline["score"] < AUTO_MERGE_THRESHOLD
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {e["auto"] for e in events if e["type"] == "FactsMerged"} == {True}  # the event log says the import merged, not the user
