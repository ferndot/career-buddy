"""Writing a resume or a cover letter by a tool-calling chat model, as a small LangGraph graph: model -> check -> (model -> check).

The model answers by calling one tool, `submit_document`, whose arguments are domain/written.WrittenDocument. After each submit the
application's checks (the `accept` it passes in) run in code and their result goes back to the model as the tool's reply: the texts
that were rejected and why. The model submits once more, at most (domain/coverage.MAX_REVISIONS), or the graph ends. Nothing here
decides what is allowed: the output is never trusted. The prompt lives in prompts/ as a versioned text file; change the wording there
and bump the version in the file name.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, TypedDict

import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from career_buddy.application.ports import Accept, LLMUnavailable
from career_buddy.domain.coverage import Checked, next_step
from career_buddy.domain.generation import Brief, BriefFact
from career_buddy.domain.writing_rules import rules_text
from career_buddy.domain.written import WrittenDocument

PROMPT = "document_writer_v8"
TOOL = "submit_document"
_SECTIONS = dict(re.findall(r"^### (\w+)\n(.*?)(?=^### |\Z)", (Path(__file__).parent / "prompts" / f"{PROMPT}.txt").read_text(encoding="utf-8"), re.M | re.S))
_TOOL_SPEC = {"type": "function", "function": {"name": TOOL, "description": "Submit the whole document.", "parameters": WrittenDocument.model_json_schema()}}


def system_prompt(brief: Brief) -> str:
    """The rules, the document kind's section shapes and general rules (`brief.rules`), then what is particular to this template: its section list, its own
    instructions and the resume's length, then how to answer."""
    template = [f"Template: write these sections, in this order: {', '.join(brief.sections)}."] if brief.sections else []
    if brief.template_instructions:
        template.append(f"Template instructions: {brief.template_instructions}")
    if brief.kind == "resume":
        length = "this resume is 1 page long" if brief.caps.pages == 1 else "follow the general length rule, at most 2 pages, and do not state a page count"
        template.append(f"Length: {length}. At most {brief.caps.skills} skills in all.")
    parts = [_SECTIONS["rules"], _SECTIONS[brief.kind], rules_text(brief.rules, brief.kind), "\n".join(template), _SECTIONS["output"]]
    return "\n".join(p.strip() for p in parts if p.strip())


def _facts(facts: Sequence[BriefFact]) -> dict[str, object]:
    """The facts as the writer reads them: each position with its achievements together, the skills and education as lists. Every id stays."""
    positions: dict[str, dict[str, object]] = {f.id: {"id": f.id, "title": f.text, "started": f.started, "finished": f.finished, "achievements": []} for f in facts if f.kind == "position"}
    for f in facts:
        if f.kind == "achievement":
            positions.setdefault(f.position_id, {"id": f.position_id, "achievements": []})["achievements"].append({"id": f.id, "text": f.text})  # type: ignore[attr-defined]
    summary = next(({"id": f.id, "text": f.text} for f in facts if f.kind == "summary"), None)
    return {**({"summary": summary} if summary else {}), "positions": list(positions.values()),
            "skills": [{"id": f.id, "text": f.text} for f in facts if f.kind == "skill"],
            "education": [{"id": f.id, "text": f.text, "started": f.started, "finished": f.finished} for f in facts if f.kind == "education"]}


def payload(brief: Brief, facts: Sequence[BriefFact]) -> str:
    """The user message: the context as JSON."""
    return json.dumps({
        "kind": brief.kind, "sections": list(brief.sections), "company": brief.company, "role": brief.role, "directions": brief.instructions,
        "posting": brief.posting, "job_terms": list(brief.terms), "missing_terms": list(brief.missing), "pinned": sorted(brief.pinned),
        "facts": _facts(facts),
    }, indent=1)


def report(checked: Checked) -> str:
    """The tool's reply: what passed, or each rejected text with its slot, the ids it cited and the reasons, then what is missing or thin and how
    long the document printed, with the achievements not yet used, and what to do about it."""
    if not checked.rejected and not checked.issues:
        return "Accepted. Nothing was rejected."
    failed = [{"slot": r.slot, "text": r.claim.text, "fact_ids": list(r.claim.fact_ids), "reasons": list(r.reasons)} for r in checked.rejected]
    issues = [{"text": i.text, "unused_achievement_ids": list(i.fact_ids), **({"slots": list(i.slots)} if i.slots else {})} for i in checked.issues]
    return f"{_SECTIONS['revise'].strip()}\n\n{json.dumps({'rejected': failed, 'issues': issues}, indent=1)}"


def _unavailable(error: Exception) -> LLMUnavailable:
    """The message carries the status code only: never a body, URL or key."""
    if isinstance(error, openai.APIStatusError):
        return LLMUnavailable(f"The model server answered with status {error.status_code}")
    if isinstance(error, openai.APIConnectionError):
        return LLMUnavailable("The model server could not be reached")
    return LLMUnavailable("The model server sent an answer this app could not read")


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    checked: Checked | None  # the document accepted so far
    rounds: int  # revisions done
    failed: bool  # the model did not answer a revision: the accepted document stands


class GraphDocumentWriter:
    def __init__(self, chat: BaseChatModel) -> None:
        self._chat = chat.bind_tools([_TOOL_SPEC], tool_choice=TOOL)

    async def write(self, brief: Brief, accept: Accept) -> Checked:
        """The last accepted document. LLMUnavailable when the first call gives no document; a later call that fails keeps the first."""

        async def model(state: State) -> dict[str, Any]:
            try:
                reply = await self._chat.ainvoke(state["messages"])
            except Exception as error:  # a client's own errors are many; all of them are "the model did not answer"
                if state["checked"] is None:
                    raise _unavailable(error) from error
                return {"failed": True}
            if not isinstance(reply, AIMessage) or not reply.tool_calls:
                if state["checked"] is None:
                    raise LLMUnavailable("The model did not submit a document. Check that it can call tools.")
                return {"failed": True}
            return {"messages": [reply]}

        async def check(state: State) -> dict[str, Any]:
            if state["failed"]:
                return {}
            calls = state["messages"][-1].tool_calls  # type: ignore[union-attr]
            try:
                doc = WrittenDocument.model_validate(calls[0]["args"])
            except ValidationError as error:
                if state["checked"] is None:
                    raise LLMUnavailable("The model server sent an answer this app could not read") from error
                return {"failed": True}
            checked = await accept(state["checked"], doc)
            replies = [ToolMessage(report(checked) if n == 0 else "Ignored: submit one document.", tool_call_id=c["id"]) for n, c in enumerate(calls)]
            return {"messages": replies, "checked": checked, "rounds": state["rounds"] + (state["checked"] is not None)}

        graph = StateGraph(State)
        graph.add_node("model", model)
        graph.add_node("check", check)
        graph.add_edge(START, "model")
        graph.add_edge("model", "check")
        graph.add_conditional_edges("check", lambda s: next_step(s["rounds"], s["checked"], s["failed"]), {"revise": "model", "end": END})
        start: State = {"messages": [SystemMessage(system_prompt(brief)), HumanMessage(payload(brief, brief.facts))], "checked": None, "rounds": 0, "failed": False}
        end = await graph.compile().ainvoke(start, {"recursion_limit": 6})
        assert end["checked"] is not None  # the first call either checked a document or raised
        return end["checked"]
