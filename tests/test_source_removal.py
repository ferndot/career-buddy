"""Removing a source hides its facts, except facts another source also states."""

import asyncio

from career_graph.adapters.graph.redstring_graph import RedstringFactGraph
from career_graph.application.projector import Projector
from career_graph.domain.builder import BatchBuilder
from career_graph.domain.events import FactsImported, SourceRemoved


def _batch(source: str, *titles: str):
    b = BatchBuilder(source)
    person = b.person("Ada Lovelace")
    for t in titles:
        b.position(person, t, "Acme")
    return b.build()


def test_removed_source_hides_its_facts_but_keeps_shared_ones() -> None:
    async def run():
        p = Projector(RedstringFactGraph())
        await p.project(FactsImported(_batch("a.txt", "Engineer")))
        await p.project(FactsImported(_batch("b.txt", "Analyst")))
        await p.project(SourceRemoved("a.txt"))
        titles = {f.title for f in (await p.snapshot()).facts}
        assert "Engineer" not in titles and "Analyst" in titles
        assert "Ada Lovelace" in titles  # stated by both sources, so it stays
        assert p.sources() == {"b.txt"}

    asyncio.run(run())


def test_reimporting_a_removed_source_brings_it_back() -> None:
    async def run():
        p = Projector(RedstringFactGraph())
        await p.project(FactsImported(_batch("a.txt", "Engineer")))
        await p.project(SourceRemoved("a.txt"))
        await p.project(FactsImported(_batch("a.txt", "Engineer")))
        assert "Engineer" in {f.title for f in (await p.snapshot()).facts}

    asyncio.run(run())


def test_api_graph_and_source_removal(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from career_graph.web.app import create_app

    text = "Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first published algorithm\n"
    with TestClient(create_app(tmp_path)) as client:
        client.post("/api/import/text", json={"text": text, "source": "ada.txt"})
        graph = client.get("/api/graph").json()
        assert graph["nodes"] and graph["edges"]
        assert [s["source"] for s in client.get("/api/sources").json()] == ["ada.txt"]
        assert client.delete("/api/sources/ada.txt").status_code == 204
        assert client.get("/api/sources").json() == []
        assert client.get("/api/facts").json() == []
