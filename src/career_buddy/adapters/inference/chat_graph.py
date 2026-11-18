"""The career chat as a small LangGraph graph, model -> tools -> model, streamed as AG-UI events. Stateless: each run is rebuilt from the messages the
client sends, so nothing is kept here. The model asks for tools; the application's ChatTools answer them. A write tool is never run in the run that
proposes it: that run ends with an AG-UI interrupt per write (assistant-ui shows it as a tool call waiting for approval), and the next run runs only
the writes whose `resume` entry is resolved with approved true. Any other write call is answered "Declined by the user." The prompt lives in prompts/."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from ag_ui.core import (
    AssistantMessage,
    BaseEvent,
    RunAgentInput,
    RunErrorEvent,
    Interrupt,
    RunFinishedEvent,
    RunFinishedInterruptOutcome,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    ToolMessage as AgUiToolMessage,
    UserMessage,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from career_buddy.adapters.inference.errors import model_unavailable
from career_buddy.adapters.inference.career_fields import field_guide
from career_buddy.application.chat_tools import WRITES, ChatTools, specs

PROMPT = (Path(__file__).parent / "prompts" / "career_chat_v1.txt").read_text(encoding="utf-8").replace("{fields}", field_guide())
DECLINED = "Declined by the user."
STOPPED = "I stopped looking after too many steps. Ask again with a narrower question."


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def to_langchain(messages: list[Any]) -> list[AnyMessage]:
    """The client's transcript as the model reads it: user and assistant turns, the assistant's tool calls and their results. Anything else is dropped."""
    out: list[AnyMessage] = []
    for m in messages:
        if isinstance(m, UserMessage) and isinstance(m.content, str):
            out.append(HumanMessage(m.content))
        elif isinstance(m, AssistantMessage):
            calls = [{"id": c.id, "name": c.function.name, "args": json.loads(c.function.arguments or "{}")} for c in m.tool_calls or []]
            out.append(AIMessage(m.content or "", tool_calls=calls))
        elif isinstance(m, AgUiToolMessage):
            out.append(ToolMessage(m.content, tool_call_id=m.tool_call_id))
    return out


async def settle(input: RunAgentInput, tools: ChatTools) -> tuple[list[AnyMessage], list[BaseEvent]]:
    """The transcript for the model, with every write call the client left open answered: run if the last assistant message's call has a resume entry that
    is resolved with approved true, declined otherwise. Returns the messages and the TOOL_CALL_RESULT events of the writes that were answered here."""
    answered = {m.tool_call_id for m in input.messages if isinstance(m, AgUiToolMessage)}
    approved = {r.interrupt_id for r in input.resume or [] if r.status == "resolved" and isinstance(r.payload, dict) and r.payload.get("approved") is True}
    last = max((i for i, m in enumerate(input.messages) if isinstance(m, AssistantMessage)), default=-1)
    out: list[AnyMessage] = []
    events: list[BaseEvent] = []
    for i, m in enumerate(input.messages):
        out += to_langchain([m])
        for c in (m.tool_calls or []) if isinstance(m, AssistantMessage) else []:
            if c.function.name not in WRITES or c.id in answered:
                continue
            args = json.loads(c.function.arguments or "{}")
            result = await tools.apply(c.function.name, args) if i == last and c.id in approved else DECLINED
            out.append(ToolMessage(result, tool_call_id=c.id))
            events.append(ToolCallResultEvent(message_id=str(uuid.uuid4()), tool_call_id=c.id, content=result, role="tool"))
    return out, events


def text_events(text: str) -> list[BaseEvent]:
    mid = str(uuid.uuid4())
    return [TextMessageStartEvent(message_id=mid, role="assistant"), TextMessageContentEvent(message_id=mid, delta=text), TextMessageEndEvent(message_id=mid)]


def events_of(message: AIMessage) -> list[BaseEvent]:
    """One model reply as AG-UI events: its text whole (no token streaming), then each tool call it makes."""
    events = text_events(str(message.content)) if message.content else []
    for c in message.tool_calls:
        events += [ToolCallStartEvent(tool_call_id=c["id"], tool_call_name=c["name"]), ToolCallArgsEvent(tool_call_id=c["id"], delta=json.dumps(c["args"])), ToolCallEndEvent(tool_call_id=c["id"])]
    return events


def _tools() -> list[dict]:
    """The tool specs, with edit_fact told each kind's fields from the career schema."""
    return [{**s, "function": {**s["function"], "description": f"{s['function']['description']} Fields: {field_guide()}."}} if s["function"]["name"] == "edit_fact" else s for s in specs()]


class GraphCareerChat:
    def __init__(self, chat: BaseChatModel) -> None:
        self._chat = chat.bind_tools(_tools())

    async def run(self, input: RunAgentInput, tools: ChatTools) -> AsyncIterator[BaseEvent]:
        yield RunStartedEvent(thread_id=input.thread_id, run_id=input.run_id)

        async def model(state: State) -> dict[str, Any]:
            return {"messages": [await self._chat.ainvoke(state["messages"])]}

        pending: list[Interrupt] = []  # the writes this run proposes; when there are any, the run ends after the tools node

        async def call_tools(state: State) -> dict[str, Any]:
            replies = []
            for c in state["messages"][-1].tool_calls:  # type: ignore[union-attr]
                said = await tools.describe(c["name"], c["args"]) if c["name"] in WRITES else None
                if said is not None and not said.startswith("Failed:"):
                    pending.append(Interrupt(id=c["id"], reason="tool_call", message=said, tool_call_id=c["id"]))  # no reply: the person's answer is the reply
                else:
                    replies.append(ToolMessage(said or await tools.run(c["name"], c["args"]), tool_call_id=c["id"]))
            return {"messages": replies}

        graph = StateGraph(State)
        graph.add_node("model", model)
        graph.add_node("tools", call_tools)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", lambda s: "tools" if s["messages"][-1].tool_calls else END, {"tools": "tools", END: END})  # type: ignore[union-attr]
        graph.add_conditional_edges("tools", lambda s: END if pending else "model", {"model": "model", END: END})
        history, answers = await settle(input, tools)
        for event in answers:
            yield event
        start: State = {"messages": [SystemMessage(f"{PROMPT.rstrip()}\n{await tools.context()}"), *history]}
        try:
            async for update in graph.compile().astream(start, {"recursion_limit": 12}, stream_mode="updates"):
                for out in update.values():
                    for message in out["messages"]:
                        if isinstance(message, AIMessage):
                            for event in events_of(message):
                                yield event
                        else:
                            yield ToolCallResultEvent(message_id=str(uuid.uuid4()), tool_call_id=message.tool_call_id, content=str(message.content), role="tool")
        except GraphRecursionError:
            for event in text_events(STOPPED):
                yield event
        except Exception as error:  # a client's own errors are many; all of them are "the model did not answer"
            yield RunErrorEvent(message=str(model_unavailable(error)))
            return
        outcome = RunFinishedInterruptOutcome(interrupts=pending) if pending else None
        yield RunFinishedEvent(thread_id=input.thread_id, run_id=input.run_id, outcome=outcome)
