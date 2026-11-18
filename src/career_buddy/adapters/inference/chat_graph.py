"""The career chat as a small LangGraph graph, model -> tools -> model, streamed as AG-UI events. Stateless: each run is rebuilt from the messages the
client sends, so nothing is kept here. The model asks for tools; the application's ChatTools answer them. The prompt lives in prompts/."""

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
    RunFinishedEvent,
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
from career_buddy.application.chat_tools import ChatTools, specs

PROMPT = (Path(__file__).parent / "prompts" / "career_chat_v1.txt").read_text(encoding="utf-8")
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


def text_events(text: str) -> list[BaseEvent]:
    mid = str(uuid.uuid4())
    return [TextMessageStartEvent(message_id=mid, role="assistant"), TextMessageContentEvent(message_id=mid, delta=text), TextMessageEndEvent(message_id=mid)]


def events_of(message: AIMessage) -> list[BaseEvent]:
    """One model reply as AG-UI events: its text whole (no token streaming), then each tool call it makes."""
    events = text_events(str(message.content)) if message.content else []
    for c in message.tool_calls:
        events += [ToolCallStartEvent(tool_call_id=c["id"], tool_call_name=c["name"]), ToolCallArgsEvent(tool_call_id=c["id"], delta=json.dumps(c["args"])), ToolCallEndEvent(tool_call_id=c["id"])]
    return events


class GraphCareerChat:
    def __init__(self, chat: BaseChatModel) -> None:
        self._chat = chat.bind_tools(specs())

    async def run(self, input: RunAgentInput, tools: ChatTools) -> AsyncIterator[BaseEvent]:
        yield RunStartedEvent(thread_id=input.thread_id, run_id=input.run_id)

        async def model(state: State) -> dict[str, Any]:
            return {"messages": [await self._chat.ainvoke(state["messages"])]}

        async def call_tools(state: State) -> dict[str, Any]:
            calls = state["messages"][-1].tool_calls  # type: ignore[union-attr]
            return {"messages": [ToolMessage(await tools.run(c["name"], c["args"]), tool_call_id=c["id"]) for c in calls]}

        graph = StateGraph(State)
        graph.add_node("model", model)
        graph.add_node("tools", call_tools)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", lambda s: "tools" if s["messages"][-1].tool_calls else END, {"tools": "tools", END: END})  # type: ignore[union-attr]
        graph.add_edge("tools", "model")
        start: State = {"messages": [SystemMessage(f"{PROMPT.rstrip()}\n{await tools.context()}"), *to_langchain(input.messages)]}
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
        yield RunFinishedEvent(thread_id=input.thread_id, run_id=input.run_id)
