"""The projector: revisions, merges and undo, the same on live commands and on replay."""

import asyncio
import random

from hypothesis import given, strategies as st

from career_buddy.adapters.graph.redstring_graph import RedstringFactGraph
from career_buddy.application.projector import Projector
from career_buddy.domain.events import FactRevised, FactsImported, FactsMerged
from career_buddy.domain.model import Fact, FactBatch, FactKind, Link, LinkKind

ACME_CORP, ACME, POS, PERSON = (Fact(i, k, t) for i, k, t in (
    ("o1", FactKind.ORGANIZATION, "Acme Corp"), ("o2", FactKind.ORGANIZATION, "Acme"),
    ("p1", FactKind.POSITION, "Engineer"), ("me", FactKind.PERSON, "Ada")))
IMPORT = FactsImported(FactBatch((ACME_CORP, ACME, POS, PERSON), (
    Link("me", "p1", LinkKind.HAS_POSITION), Link("p1", "o2", LinkKind.AT))))


def run(events) -> FactBatch:
    async def go() -> FactBatch:
        projector = Projector(RedstringFactGraph())
        for event in events:
            await projector.project(event)
        return await projector.snapshot()

    return asyncio.run(go())


def test_revision_replaces_title_and_attributes_and_beats_a_later_reimport() -> None:
    revised = FactRevised("p1", "Staff Engineer", {"hidden": "true"})
    for events in ([IMPORT, revised], [IMPORT, revised, IMPORT]):
        fact = next(f for f in run(events).facts if f.id == "p1")
        assert (fact.title, fact.attributes, fact.kind) == ("Staff Engineer", {"hidden": "true"}, FactKind.POSITION)


def test_merge_rewires_links_and_hides_the_alias_and_undo_restores_both() -> None:
    merged = run([IMPORT, FactsMerged("o2", "o1")])
    assert "o2" not in {f.id for f in merged.facts}
    assert Link("p1", "o1", LinkKind.AT) in merged.links and Link("p1", "o2", LinkKind.AT) not in merged.links
    assert run([IMPORT, FactsMerged("o2", "o1"), FactsMerged("o2", "o1", undo=True)]) == run([IMPORT])


def test_merges_chain_and_a_reimport_does_not_resurrect_the_alias() -> None:
    org3 = FactsImported(FactBatch((Fact("o3", FactKind.ORGANIZATION, "Acme Inc"),)))
    events = [IMPORT, org3, FactsMerged("o2", "o1"), FactsMerged("o1", "o3"), IMPORT]
    snapshot = run(events)
    assert {f.id for f in snapshot.facts if f.kind == FactKind.ORGANIZATION} == {"o3"}
    assert Link("p1", "o3", LinkKind.AT) in snapshot.links


@given(st.dictionaries(st.sampled_from(["o1", "o2", "p1", "me"]), st.text(max_size=5), max_size=4),
       st.randoms(use_true_random=False))
def test_replay_of_revisions_is_order_independent_per_fact(titles: dict[str, str], rnd: random.Random) -> None:
    events = [IMPORT, *(FactRevised(i, t, {"k": t}) for i, t in titles.items())]
    shuffled = list(events)
    rnd.shuffle(shuffled)  # the import may land after the revisions
    assert run(events) == run(shuffled)
