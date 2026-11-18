"""The tools the career chat may call, and the short context it starts from. Read tools answer from CareerQueries as JSON text, so the chat sees what
the career screen sees. Write tools (add, edit and delete a fact) go through EditService, so the event log stays the truth; they run only through
`apply`, which the chat calls after the person approved the change `describe` showed. A bad argument or an unknown id is a "Failed: ..." answer,
never an exception, so the model can explain it."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from career_buddy.application.ports import FactNotFound, SourceBusy
from career_buddy.application.services import EDITABLE_LINKS, CareerQueries, EditService
from career_buddy.domain.dates import checked
from career_buddy.domain.model import FactKind, InvalidFact, normalize

MAX_FACTS = 25
MAX_SKILLS = 200


class FindFacts(BaseModel):
    query: str = ""  # words to look for in the title and the attributes; empty matches every fact of the kind
    kind: FactKind | None = None


class FactRef(BaseModel):
    fact_id: str


class NoArguments(BaseModel):
    pass


class AddFact(BaseModel):
    kind: Literal["Position", "Achievement", "Skill", "Education"]
    title: str  # a position's title, the achievement's text, the skill's name, the degree
    parent_id: str | None = None  # an achievement needs its position's id; the others go under the person
    attributes: dict[str, str] = {}  # for example organization, started, finished (YYYY or YYYY-MM)


class EditFact(BaseModel):
    fact_id: str  # the person's id edits the summary
    title: str | None = None
    changes: dict[str, str] = {}  # attributes to set; an empty value removes the attribute; the others stay


class MergeFacts(BaseModel):
    canonical_id: str  # the fact that stays
    alias_ids: list[str] = Field(min_length=1)  # the facts that are shown as it from now on


class MergedPair(BaseModel):
    alias_id: str
    canonical_id: str  # as list_merges shows it


class Relationship(BaseModel):
    source_id: str  # AT: position -> organization; ATTENDED: education -> organization; USES_SKILL: position or achievement -> skill; ACHIEVED: position -> achievement
    target_id: str
    kind: Literal["AT", "ATTENDED", "USES_SKILL", "ACHIEVED"]


class SourceName(BaseModel):
    source: str  # as list_sources shows it


APPROVAL = " Needs the person's approval; nothing changes until they approve. Only write what the person said or confirmed in this conversation."


TOOLS: dict[str, tuple[str, type[BaseModel]]] = {
    "find_facts": (f"List or search career facts (at most {MAX_FACTS}), optionally of one kind. Use it to find ids.", FindFacts),
    "get_position": ("Show one position with its organization and its achievements.", FactRef),
    "list_skills": ("List every skill.", NoArguments),
    "list_sources": ("List the sources the facts came from, with how many facts each gave.", NoArguments),
    "get_relationships": ("Show every link of one fact: what it is linked to, and how.", FactRef),
    "list_merges": ("List the merges that can be undone: the fact kept and the fact now shown as it, automatic merges included.", NoArguments),
    "add_fact": ("Add a position, achievement, skill or education." + APPROVAL, AddFact),
    "edit_fact": ("Change a fact. Get fact_id from find_facts or get_position, never invent it. Pass only what changes: title and changes. "
                  "Ask the person first when a value is unclear or missing." + APPROVAL, EditFact),
    "delete_fact": ("Delete one fact for good; it cannot be undone." + APPROVAL, FactRef),
    "merge_facts": ("Merge facts of one kind into one kept fact; the others are shown as it. Can be undone with unmerge_fact." + APPROVAL, MergeFacts),
    "unmerge_fact": ("Undo one merge, as list_merges shows it." + APPROVAL, MergedPair),
    "add_relationship": ("Link two facts: a position AT an organization, education ATTENDED an organization, a position or achievement USES_SKILL a skill, a position ACHIEVED an achievement." + APPROVAL, Relationship),
    "remove_relationship": ("Remove one such link between two facts." + APPROVAL, Relationship),
    "remove_source": ("Remove a source the person registered; the facts only it stated are hidden." + APPROVAL, SourceName),
}
WRITES = {"add_fact", "edit_fact", "delete_fact", "merge_facts", "unmerge_fact", "add_relationship", "remove_relationship", "remove_source"}


def specs() -> list[dict[str, Any]]:
    """The tools as an OpenAI-style tool list; the argument models' JSON schema is the spec."""
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": m.model_json_schema()}} for n, (d, m) in TOOLS.items()]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class ChatTools:
    def __init__(self, queries: CareerQueries, edits: EditService, on_source_removed: Callable[[str], None] = lambda _: None) -> None:
        self._queries = queries
        self._edits = edits
        self._on_source_removed = on_source_removed  # the web layer drops the source's import log, as DELETE /api/sources does

    async def _facts(self, kind: FactKind | None = None) -> list[dict[str, Any]]:
        return [f for f in await self._queries.facts(kind) if f["attributes"].get("hidden") != "true"]  # type: ignore[attr-defined]

    async def run(self, name: str, arguments: dict[str, Any]) -> str:
        """A read tool's answer. A write tool is refused here: it runs only through `apply`, after approval."""
        if name in WRITES:
            return "Failed: this change needs the person's approval first"
        return await self._call("_", name, arguments)

    async def _call(self, prefix: str, name: str, arguments: dict[str, Any]) -> str:
        """Validates the arguments and runs `_<name>` (prefix "_") or `_describe_<name>`; a bad call is a Failed answer."""
        if name not in TOOLS:
            return f"Failed: there is no tool called {name}"
        try:
            args = TOOLS[name][1].model_validate(arguments)
            return await getattr(self, f"{prefix}{name}")(args)
        except ValidationError as error:
            return f"Failed: {'; '.join(e['msg'] for e in error.errors())}"
        except (FactNotFound, InvalidFact, SourceBusy) as error:
            return f"Failed: {error}"

    async def describe(self, name: str, arguments: dict[str, Any]) -> str:
        """The exact change a write tool would make, in words, for the approval card; "Failed: ..." when it cannot be made."""
        return await self._call("_describe_", name, arguments) if name in WRITES else f"Failed: {name} is not a write tool"

    async def apply(self, name: str, arguments: dict[str, Any]) -> str:
        """Runs a write tool the person approved: "Changed: <what describe said>", or "Failed: ..." with nothing changed."""
        said = await self.describe(name, arguments)
        if said.startswith("Failed:"):
            return said
        done = await self._call("_", name, arguments)
        return done if done.startswith("Failed:") else f"Changed: {said}"

    async def _fact(self, fact_id: str) -> dict[str, Any]:
        found = next((f for f in await self._queries.facts(None) if f["id"] == fact_id), None)
        if found is None:
            raise FactNotFound(f"no fact has the id {fact_id}")
        return found  # type: ignore[return-value]

    async def _parent(self, args: AddFact) -> dict[str, Any]:
        if args.kind == "Achievement":
            if not args.parent_id:
                raise InvalidFact("an achievement needs parent_id, the id of its position")
            return await self._fact(args.parent_id)
        person = next(iter(await self._facts(FactKind.PERSON)), None)
        if person is None:
            raise InvalidFact("import a resume or LinkedIn export first, so there is a person to add to")
        return person

    async def _describe_add_fact(self, args: AddFact) -> str:
        parent = await self._parent(args)
        checked(args.attributes)
        where = f" under {parent['kind']} '{parent['title']}'" if args.kind == "Achievement" else ""
        shown = "".join(f"; {k} {v}" for k, v in args.attributes.items() if k != "description")
        return f"Add {args.kind} '{args.title}'{where}{shown}"

    async def _add_fact(self, args: AddFact) -> str:
        parent = await self._parent(args)
        # a position's description would be read into achievements by the model: a write nobody approved, so it is dropped
        attributes = {k: v for k, v in args.attributes.items() if k != "description"}
        await self._edits.add_fact(FactKind(args.kind), args.title, parent["id"], attributes)
        return "Done"

    async def _revision(self, args: EditFact) -> tuple[str, str, dict[str, str], list[str]]:
        """The fact's description, its new title, its new attributes (changes merged onto the current ones, empty values removed), and each difference in words."""
        fact = await self._fact(args.fact_id)
        title = args.title.strip() if args.title is not None else fact["title"]
        old = fact["attributes"]
        new = checked({k: v for k, v in {**old, **args.changes}.items() if v.strip()}, old)
        said = [f"title '{fact['title']}' -> '{title}'"] if title != fact["title"] else []
        for key in sorted(old.keys() | new.keys()):
            before, after = old.get(key), new.get(key)
            if before != after:
                said.append(f"{key} '{before}' -> '{after}'" if before and after else f"{key} removed (was '{before}')" if before else f"{key} set to '{after}'")
        if not said:
            raise InvalidFact("that changes nothing")
        return f"{fact['kind']} '{fact['title']}'", title, new, said

    async def _describe_edit_fact(self, args: EditFact) -> str:
        what, _, _, said = await self._revision(args)
        return f"{what}: " + "; ".join(said)

    async def _edit_fact(self, args: EditFact) -> str:
        _, title, attributes, _ = await self._revision(args)
        await self._edits.revise(args.fact_id, title, attributes)
        return "Done"

    async def _describe_delete_fact(self, args: FactRef) -> str:
        fact = await self._fact(args.fact_id)
        return f"Delete {fact['kind']} '{fact['title']}' for good. This cannot be undone."

    async def _delete_fact(self, args: FactRef) -> str:
        await self._edits.delete(args.fact_id)
        return "Done"

    async def _merge_plan(self, args: MergeFacts) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """The kept fact and the facts merged into it, checked together first so a merge of several is approved whole and never half done (the service's rules)."""
        kept = await self._fact(args.canonical_id)
        aliases = [await self._fact(i) for i in dict.fromkeys(args.alias_ids)]
        if any(a["id"] == kept["id"] for a in aliases):
            raise InvalidFact("A fact cannot be merged into itself")
        if any(a["kind"] != kept["kind"] for a in aliases):
            raise InvalidFact("Only facts of the same kind can be merged")
        return kept, aliases

    async def _describe_merge_facts(self, args: MergeFacts) -> str:
        kept, aliases = await self._merge_plan(args)
        return (f"Merge into {kept['kind']} '{kept['title']}' (kept):\n" + "\n".join(f"- '{a['title']}'" for a in aliases)
                + f"\nThey are shown as '{kept['title']}' from now on. This can be undone.")

    async def _merge_facts(self, args: MergeFacts) -> str:
        kept, aliases = await self._merge_plan(args)
        for a in aliases:
            await self._edits.merge(a["id"], kept["id"], False)
        return "Done"

    async def _merged(self, args: MergedPair) -> dict[str, Any]:
        found = next((m for m in await self._queries.merges() if (m["alias"]["id"], m["canonical"]["id"]) == (args.alias_id, args.canonical_id)), None)  # type: ignore[index]
        if found is None:
            raise FactNotFound("those two are not merged; list_merges shows what can be undone")
        return found

    async def _describe_unmerge_fact(self, args: MergedPair) -> str:
        found = await self._merged(args)
        return f"Show '{found['alias']['title']}' separately from '{found['canonical']['title']}' again"

    async def _unmerge_fact(self, args: MergedPair) -> str:
        await self._merged(args)
        await self._edits.merge(args.alias_id, args.canonical_id, True)
        return "Done"

    async def _list_merges(self, _: NoArguments) -> str:
        return _dump(await self._queries.merges())

    async def _relationship(self, args: Relationship, adding: bool) -> str:
        """The link in words. The kinds that fit are EditService's (EDITABLE_LINKS); an add that is there already, or a remove of one that is not, changes nothing."""
        source, target = await self._fact(args.source_id), await self._fact(args.target_id)
        if (FactKind(source["kind"]), FactKind(target["kind"])) not in EDITABLE_LINKS[args.kind]:
            raise InvalidFact(f"{args.kind} links " + " or ".join(f"a {a} to a {b}" for a, b in EDITABLE_LINKS[args.kind]))
        _, links = await self._links(args.source_id)
        present = any(link["kind"] == args.kind and link["direction"] == "out" and link["other_id"] == args.target_id for link in links)
        if present == adding:
            raise InvalidFact("those are linked that way already" if adding else "those are not linked that way")
        return f"{source['kind']} '{source['title']}' and {target['kind']} '{target['title']}' ({args.kind})"

    async def _describe_add_relationship(self, args: Relationship) -> str:
        return "Link " + await self._relationship(args, True)

    async def _add_relationship(self, args: Relationship) -> str:
        await self._relationship(args, True)
        await self._edits.add_link(args.source_id, args.target_id, args.kind)
        return "Done"

    async def _describe_remove_relationship(self, args: Relationship) -> str:
        return "Unlink " + await self._relationship(args, False)

    async def _remove_relationship(self, args: Relationship) -> str:
        await self._relationship(args, False)
        await self._edits.remove_link(args.source_id, args.target_id, args.kind)
        return "Done"

    async def _describe_remove_source(self, args: SourceName) -> str:
        found = next((s for s in await self._queries.sources() if s["source"] == args.source), None)
        if found is None:
            raise FactNotFound(f"there is no source called {args.source}; list_sources shows them")
        return f"Remove source '{args.source}'. Its {found['facts']} facts are hidden unless another source states them."

    async def _remove_source(self, args: SourceName) -> str:
        await self._edits.remove_source(args.source)
        self._on_source_removed(args.source)
        return "Done"

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
