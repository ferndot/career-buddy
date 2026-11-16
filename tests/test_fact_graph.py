"""The in-memory FactGraph adapter keeps the port contract: apply is an idempotent upsert."""

import asyncio

from career_graph.adapters.graph.redstring_graph import RedstringFactGraph
from career_graph.domain.model import Fact, FactBatch, FactKind, Link, LinkKind


def test_apply_then_snapshot_round_trips_facts_and_links() -> None:
    graph = RedstringFactGraph()
    batch = FactBatch(
        (Fact("a", FactKind.PERSON, "Ada"), Fact("b", FactKind.SKILL, "Python")),
        (Link("a", "b", LinkKind.HAS_SKILL),),
    )
    asyncio.run(graph.apply(batch))
    snapshot = asyncio.run(graph.snapshot())
    assert snapshot.facts == batch.facts
    assert snapshot.links == batch.links


def test_apply_twice_does_not_duplicate_and_later_fact_wins() -> None:
    graph = RedstringFactGraph()
    link = Link("a", "b", LinkKind.HAS_SKILL)
    skill = Fact("b", FactKind.SKILL, "Python")
    asyncio.run(graph.apply(FactBatch((Fact("a", FactKind.PERSON, "Ada"), skill), (link,))))
    asyncio.run(graph.apply(FactBatch((Fact("a", FactKind.PERSON, "Ada L"),), (link,))))
    snapshot = asyncio.run(graph.snapshot())
    assert [f.title for f in snapshot.facts] == ["Ada L", "Python"]
    assert snapshot.links == (link,)
