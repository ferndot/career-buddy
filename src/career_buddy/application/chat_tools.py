"""The tools the career chat may call, and the short context it starts from. Read-only: each tool answers from CareerQueries as JSON text, so the
chat sees what the career screen sees. A bad argument or an unknown id is a "Failed: ..." answer, never an exception, so the model can explain it."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from career_buddy.application.services import CareerQueries
from career_buddy.domain.model import FactKind, normalize

MAX_FACTS = 25
MAX_SKILLS = 200


class FindFacts(BaseModel):
    query: str = ""  # words to look for in the title and the attributes; empty matches every fact of the kind
    kind: FactKind | None = None


class FactRef(BaseModel):
    fact_id: str


class NoArguments(BaseModel):
    pass


TOOLS: dict[str, tuple[str, type[BaseModel]]] = {
    "find_facts": (f"List or search career facts (at most {MAX_FACTS}), optionally of one kind. Use it to find ids.", FindFacts),
    "get_position": ("Show one position with its organization and its achievements.", FactRef),
    "list_skills": ("List every skill.", NoArguments),
    "list_sources": ("List the sources the facts came from, with how many facts each gave.", NoArguments),
    "get_relationships": ("Show every link of one fact: what it is linked to, and how.", FactRef),
}


def specs() -> list[dict[str, Any]]:
    """The tools as an OpenAI-style tool list; the argument models' JSON schema is the spec."""
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": m.model_json_schema()}} for n, (d, m) in TOOLS.items()]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class ChatTools:
    def __init__(self, queries: CareerQueries) -> None:
        self._queries = queries

    async def _facts(self, kind: FactKind | None = None) -> list[dict[str, Any]]:
        return [f for f in await self._queries.facts(kind) if f["attributes"].get("hidden") != "true"]  # type: ignore[attr-defined]

    async def run(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in TOOLS:
            return f"Failed: there is no tool called {name}"
        try:
            args = TOOLS[name][1].model_validate(arguments)
        except ValidationError as error:
            return f"Failed: {'; '.join(e['msg'] for e in error.errors())}"
        return await getattr(self, f"_{name}")(args)

    async def _find_facts(self, args: FindFacts) -> str:
        wanted = normalize(args.query)
        found = [f for f in await self._facts(args.kind) if wanted in normalize(" ".join([f["title"], *f["attributes"].values()]))]  # type: ignore[arg-type]
        return _dump({"total": len(found), "facts": found[:MAX_FACTS]})

    async def _list_skills(self, _: NoArguments) -> str:
        skills = await self._facts(FactKind.SKILL)
        return _dump({"total": len(skills), "skills": [{"id": s["id"], "title": s["title"]} for s in skills[:MAX_SKILLS]]})

    async def _list_sources(self, _: NoArguments) -> str:
        return _dump([{k: s[k] for k in ("source", "facts", "status")} for s in await self._queries.sources()])

    async def _links(self, fact_id: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
        """The fact (None if unknown) and its links, each with the other end's title."""
        graph = await self._queries.graph()
        nodes = {n["id"]: n for n in graph["nodes"]}
        links = [{"kind": str(e["kind"]), "direction": "out" if e["source"] == fact_id else "in", "other_id": str(other), "other_title": str(nodes[other]["title"]),
                  "other_kind": str(nodes[other]["kind"])}
                 for e in graph["edges"] if fact_id in (e["source"], e["target"]) and (other := e["target"] if e["source"] == fact_id else e["source"]) in nodes]
        return nodes.get(fact_id), links

    async def _get_relationships(self, args: FactRef) -> str:
        fact, links = await self._links(args.fact_id)
        return _dump({"fact": fact, "links": links}) if fact else f"Failed: no fact has the id {args.fact_id}"

    async def _get_position(self, args: FactRef) -> str:
        position = next((f for f in await self._facts(FactKind.POSITION) if f["id"] == args.fact_id), None)
        if position is None:
            return f"Failed: no position has the id {args.fact_id}"
        _, links = await self._links(args.fact_id)
        achievements = [{"id": link["other_id"], "text": link["other_title"]} for link in links if link["kind"] == "ACHIEVED"]
        organization = next((link["other_title"] for link in links if link["kind"] == "AT"), None)
        return _dump({"position": position, "organization": organization, "achievements": achievements})

    async def context(self) -> str:
        """What the chat knows before it calls a tool: who the person is, how many facts of each kind, and each position with its id."""
        graph = await self._queries.graph()
        nodes = {n["id"]: n for n in graph["nodes"]}
        counts: dict[str, int] = {}
        for n in nodes.values():
            counts[str(n["kind"])] = counts.get(str(n["kind"]), 0) + 1
        person = next((f for f in await self._facts(FactKind.PERSON)), None)
        lines = [f"Person: {person['title']} ({person['attributes'].get('summary', 'no summary')})" if person else "Person: none yet (nothing is imported)",  # type: ignore[attr-defined]
                 "Facts: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none")]
        for f in (await self._facts(FactKind.POSITION))[:30]:
            org = next((nodes[e["target"]]["title"] for e in graph["edges"] if e["kind"] == "AT" and e["source"] == f["id"] and e["target"] in nodes), "")
            lines.append(f"Position {f['id']} | {f['title']} | {org} | {f['attributes'].get('started', '')} - {f['attributes'].get('finished', '')}")  # type: ignore[attr-defined]
        return "\n".join(lines)
