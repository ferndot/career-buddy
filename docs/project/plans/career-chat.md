---
title: Career chat in a sidebar that edits career data through approved tools
status: Phase 0, 1 and 2 done (see career-chat-phase0.md)
date: 2026-11-17
target_bc: career editing (application/services.py, new application/chat_tools.py), inference adapter (new adapters/inference/chat_graph.py), web (new web/chat_routes.py), frontend shell (new frontend/src/components/chat/)
depends_on: none
---

# Career chat in a sidebar

## Goal

You chat about your career in a sidebar. The chat reads your career facts and changes them through tools. It covers:

- facts: positions, achievements, skills, education, and the summary
- sources
- merges, including undoing a merge
- relationships (links)

Every change goes through the existing `EditService`, so the event log stays the source of truth. No change is silent, and
nothing is written until you approve it in the chat.

Minimal means one backend route, one LangGraph loop, one tools module, and one sidebar. There is no checkpointer, no chat
persistence on the server, and no new domain events.

## The stack and what each part does

| Part | Used for | Not used for |
|---|---|---|
| **LangGraph** (installed: `langgraph`, `langchain-core`, `langchain-openai`) | The agent loop on the backend. A `StateGraph` with two nodes, `model -> tools -> model`, the same shape as `writer_graph.py`. Tool calling goes through `chat.bind_tools(...)` on the connection's existing `chat_model(...)`. | Persistence. There is no checkpointer and no `interrupt()`. Each run rebuilds the conversation from the messages the client sends. |
| **AG-UI** (`ag-ui-protocol` on PyPI; `@ag-ui/client` on npm) | The wire protocol. The client sends `POST /api/chat` with a `RunAgentInput` body. The server answers with an SSE stream of AG-UI events, built with `ag_ui.core` event models and `ag_ui.encoder.EventEncoder`. An approval is an AG-UI **interrupt**: the run ends with `RUN_FINISHED` whose `outcome` is an interrupt. The answer comes back in the next run as `RunAgentInput.resume`. | Shared agent state (`STATE_SNAPSHOT`) and custom events. Neither is needed. |
| **assistant-ui** (`@assistant-ui/react`, `@assistant-ui/react-ag-ui`) | The chat thread inside the sidebar: `useAgUiRuntime({ agent: new HttpAgent({ url }) })`, plus the headless primitives `ThreadPrimitive`, `MessagePrimitive` and `ComposerPrimitive`. It handles message state, the composer, and parsing the event stream into message parts. | Styling. There is no Tailwind, no shadcn CLI, and no styled `Thread` component. Primitives are styled with Chakra through `asChild`. |
| **Chakra v3** (installed) | The panel, header and toggle button around the thread; message bubbles; the **tool-result card**, one fallback component for every tool call; the **approval card**, the same tool-call fallback with Apply and Decline buttons that call assistant-ui's `respondToApproval({ approved })` (phase 0: this is how an interrupt with `reason: "tool_call"` reaches the card, so `useAgUiInterrupts` is only for the count); and the error notice ("Connect a model in Settings"). | n/a |

### Verified (2026-11-17, from the official docs)

- **assistant-ui has an AG-UI runtime: `@assistant-ui/react-ag-ui`.** It provides `useAgUiRuntime({ agent })`, takes any
  `AbstractAgent` such as `HttpAgent` from `@ag-ui/client`, works with React 18 or 19, and is built on
  `ExternalStoreRuntime`. Interrupts are read with `useAgUiInterrupts` and answered with
  `useAgUiSubmitInterruptResponses`. Each answer is `{ interruptId, status: "resolved" | "cancelled" }`, and the answers
  must cover every open interrupt. Interrupts are marked experimental, and the older `unstable_*` names are deprecated.
  By default a resume sends the full transcript (`resumeTranscript: "full"`).
- **The AG-UI Python SDK fits FastAPI.** `ag-ui-protocol` 1.0.0 (Python >=3.9, pydantic) is types plus an encoder, with
  no framework of its own. The bridge is one FastAPI route:
  1. Parse `RunAgentInput` (it is a pydantic model).
  2. Return `StreamingResponse(gen(), media_type=encoder.get_content_type())`.
  3. Make each item of `gen()` an `encoder.encode(event)`.

  `RunAgentInput` has `messages` (user, assistant with `tool_calls`, and tool messages with `tool_call_id`), `tools`,
  `state`, `context` and `resume`.
- **Rejected: `ag-ui-langgraph` (`add_langgraph_fastapi_endpoint`).** Its docs require a checkpointer on the graph, and
  its signature differs between versions and sources. A 2-node graph that rebuilds from the client's messages is
  smaller.
- **No longer applies:** the earlier research on LocalRuntime, `ChatModelAdapter`, `defineToolkit`, `externalTool`,
  `unstable_humanToolNames` and the Vercel data-stream header. The AG-UI runtime replaces all of it.

### Phase 0 result: all four passed; see [career-chat-phase0.md](career-chat-phase0.md). Changes it made to this plan are marked "(phase 0)".

### Was not verified (checked in phase 0)

1. The installed Python `RunFinishedEvent` carries `outcome` with interrupts. The type reference shows `resume` on the
   input but does not show the outcome field.
2. On the next run, assistant-ui sends backend tool calls and their `TOOL_CALL_RESULT`s back in
   `RunAgentInput.messages`. The stateless loop depends on this.
3. A tool-call `Fallback` passed to `MessagePrimitive.Parts components={{ tools: { Fallback } }}` renders under the
   AG-UI runtime, and the primitives render inside the Chakra provider without style conflicts.
4. The Vite dev proxy (`/api` -> 127.0.0.1:8000 in `frontend/vite.config.ts`) streams SSE without buffering. In the
   built app, the API serves the UI, so the URL is the same origin.

(phase 0: check 1 passed, so the fallback below is not needed.) If check 1 fails, the fallback is to end the run with `RUN_FINISHED.pendingToolCallIds` listing the write calls. The
approval card then answers with `addToolResult("approved" | "declined")` instead of interrupts. Only the card's two
buttons and the backend's resume reading change.

## Architecture

```
Sidebar (assistant-ui primitives + Chakra)
  -> useAgUiRuntime(HttpAgent url = apiUrl('/api/chat'))
  -> POST /api/chat  RunAgentInput {messages, resume?}     (web/chat_routes.py)
  -> GraphCareerChat.run(input, tools) -> AsyncIterator[AG-UI event]   (adapters/inference/chat_graph.py)
       1. apply resume: run approved write calls through ChatTools; declined ones get "Declined by the user."
       2. LangGraph: model -> (read tools run here) -> model ... until a text answer or a write call
       3. write call(s): emit TOOL_CALL_*; end with RUN_FINISHED outcome=interrupt, one interrupt per write call
  -> ChatTools.run(name, args) -> EditService / CareerQueries      (application/chat_tools.py)
```

### One run, as events

1. `RUN_STARTED`.
2. For each resumed write call: `TOOL_CALL_RESULT`, either `Changed: …` or `Declined by the user.`
3. For each model reply: `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` when it has text, and
   `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END` per call.
4. Each read call that runs: `TOOL_CALL_RESULT`.
5. `RUN_FINISHED`. When a write is waiting, its `outcome` is `{type: "interrupt", interrupts: [{id: <tool_call_id>,
   toolCallId, message: <describe text>}]}`.
6. On a model failure: `RUN_ERROR`, carrying the `LLMUnavailable` text.

Text is sent whole for each model reply: one `CONTENT` event per message. Token streaming is a later step (see Phases).

### Rules

- **Stateless.** The server keeps nothing between runs. The client sends the transcript, which assistant-ui holds in
  memory for the tab.
- **Trust.** A client-sent transcript can be edited, but the client is the same local user who can already call
  `PATCH /api/facts`, so no new power is granted.
- **Write calls never run in the same run they are proposed in.** Only a `resume` entry with `status: "resolved"` and `payload.approved === true` (phase 0: a decline is also `resolved`, with `approved: false`) whose
  `interrupt_id` matches a write call in the last assistant message runs it. Any write call without a matching resolved
  entry is answered `Declined by the user.`
- **One model connection.** `LLMConnections.inference()` builds `chat_model(...)` once and passes it to both
  `GraphDocumentWriter` and `GraphCareerChat`. `Inference` gains a `chat` field, and `composition.current("chat")` reads
  it at each request, so a changed connection in Settings applies at once. With no connection, the route sends
  `RUN_ERROR` with "Connect a model in Settings to chat about your career."
- **Loop bound.** `recursion_limit` 12, at most about 5 rounds of reads. When it is hit, the run ends with a short text
  answer, not an error.

### How the chat sees the career

The chat gets a short context in the system prompt, not the whole career. `ChatTools.context()` builds it, at most about
2 KB:

- the Person fact's id, name and summary
- a count of facts of each kind
- each position as `id | title | organization | dates` (at most 30)

Everything else comes through read tools. Results are capped: `find_facts` returns at most 25 facts. The prompt lives in
`adapters/inference/prompts/career_chat_v1.txt`, versioned like the writer's.

## Tools

Arguments are pydantic models, and their JSON schema is the tool spec, the same way the writer builds `_TOOL_SPEC`. The
kinds are limited to `Position | Achievement | Skill | Education` for adds. Link kinds are limited to the keys of
`EDITABLE_LINKS`: `AT`, `ATTENDED`, `USES_SKILL`, `ACHIEVED`.

### Read tools (run at once, no approval)

| Tool | Arguments | Calls | Returns |
|---|---|---|---|
| `find_facts` | `query: str = ""`, `kind: FactKind \| None` | `CareerQueries.facts(kind)`, filtered by normalised substring over title and attribute values | Up to 25 `{id, kind, title, attributes, source}` |
| `get_fact` | `fact_id` | Snapshot | The fact, plus its links as `{kind, direction, other_id, other_title}` |
| `list_sources` | none | `CareerQueries.sources()` | Name, fact count and status |
| `list_duplicates` | none | `CareerQueries.duplicates()` | Suggested pairs, with the canonical id |
| `list_merges` | none | New `CareerQueries.merges()`, a wrapper over the existing `Projector.absorbed()` | `{canonical: {id, title}, alias: {id, title}}`, covering automatic merges too |

### Write tools (need approval; the run ends with an interrupt)

| Tool | Arguments | Calls | Approval card text (`describe`) |
|---|---|---|---|
| `add_fact` | `kind`, `title`, `parent_id?`, `attributes: dict[str,str] = {}` | `EditService.add_fact` | "Add Achievement 'X' under Position 'Y'", with attributes listed |
| `edit_fact` | `fact_id`, `title?`, `changes: dict[str,str]` (an empty value removes the key) | `EditService.revise(id, title, {**current, **changes})` | "Position 'Y': title 'A' -> 'B'; started '2019' -> '2018'" (before and after) |
| `delete_fact` | `fact_id` | `EditService.delete` | "Delete Position 'Y' for good. Its N achievements go with it. This cannot be undone." |
| `merge_facts` | `alias_id`, `canonical_id` | `EditService.merge(..., undo=False)` | "Show 'A' as 'B' (merge). It can be undone." |
| `undo_merge` | `alias_id`, `canonical_id` | `EditService.merge(..., undo=True)` | "Show 'A' separately from 'B' again" |
| `add_link` | `source_id`, `target_id`, `kind` | `EditService.add_link` | "Link Achievement 'X' to Position 'Y' (ACHIEVED)" |
| `remove_link` | `source_id`, `target_id`, `kind` | `EditService.remove_link` | "Unlink …" |
| `remove_source` | `source` | `EditService.remove_source`, then `source_log.drop(source)` (the same pair as `DELETE /api/sources`) | "Remove source 'cv.pdf'. Its N facts are hidden unless another source states them." |

### Details found in the code

- **`add_fact` drops `description`.** `EditService.add_fact` would otherwise read a position's description into
  achievements with the model, which would be a write the user never approved. Each achievement is its own approved
  `add_fact` under the position.
- **`add_fact` finds the Person parent itself** for Position, Skill and Education, because `manual_fact` needs one.
  Achievement needs `parent_id`, a position. On an empty career with no Person, the tool answers `Failed: import a
  resume or LinkedIn export first`, so the chat does not invent a person.
- **The summary is `Person.attributes["summary"]`.** Editing it is `edit_fact` on the Person with
  `changes={"summary": …}`. The Person id is in the context. Hiding a fact is `edit_fact` with `{"hidden": "true"}`.
- **`edit_fact` merges changes onto the current attributes,** because `revise` is a full replacement and a model that
  sends only the changed keys would wipe the rest.
- **Errors become tool results, not HTTP errors.** `FactNotFound`, `InvalidFact`, `SourceBusy` and pydantic
  `ValidationError` are caught in `ChatTools.run` and returned as `Failed: <message>`, so the model can explain and the
  card shows it.
- **Result text after a write** is `Changed: <describe text>`, read again from the snapshot after the write.

Skipped, because nobody asked for them: dismissing a duplicate, adding a source by chat, reordering, and importing text.

## Keeping the UI in sync

No protocol extension is needed. `ChatSidebar` watches the runtime's running state. When a run finishes, it invalidates
the career queries only: `['facts']`, `['graph']`, `['duplicates']`, `['sources']` and `['profile']` if present. It does
not invalidate globally, because `details-preview` is a POST-backed query that would re-render a document. A read-only
run causes a cheap localhost refetch, which is accepted to keep the logic to one effect.

## Safety

1. **No silent change.** Every write is a tool-call card showing the arguments, then an approval card with the
   `describe` text, then the same card showing `Changed: …` or `Declined` once it has run. The card stays in the thread.
2. **Approval before writes.** Enforced on the server: a write runs only from a matching `resume` entry with
   `status: "resolved"`. The composer is disabled while an approval card is open. assistant-ui throws if you send while
   an interrupt is open, and that avoids the case entirely.
3. **No invented facts.**
   - The system prompt says to write only what the user said or confirmed in this conversation, and to ask when unsure.
   - The real guard is that the approval card shows the exact text before anything is written. Model wording cannot be
     enforced in code, so the user's approval is the check.
   - `add_fact` drops `description`, so no second model call adds unseen achievements.
4. **Destructive actions say so.** The cards for `delete_fact` and `remove_source` say what goes with them and that a
   delete cannot be undone.
5. **No key, URL or body in errors.** Reuse `writer_graph._unavailable` (move it to `adapters/inference/errors.py`,
   which exists) so `RUN_ERROR` carries the status code only.

## Testing

All tests use public front doors. The model is faked at the HTTP level, the same way as `tests/test_generate_api.py`:
`create_app(tmp_path, llm_transport=httpx.MockTransport(scripted))` plus `connect_mock`. The scripted transport answers
with OpenAI-shaped `choices[0].message.tool_calls`, records each request body, and replies in order.

### Backend: `tests/test_chat_api.py` (POST /api/chat, then GET /api/facts and friends)

1. **Read.** The model calls `find_facts`, then answers. The stream has `TOOL_CALL_RESULT` and text, there is no
   interrupt, and the second model request contains the found fact's title.
2. **Propose.** The model calls `edit_fact`. The run ends with an interrupt whose message shows before and after.
   `GET /api/facts` is unchanged, so nothing is written before approval.
3. **Approve.** The same transcript plus `resume=[resolved]`. `GET /api/facts` shows the change. A new `create_app` on
   the same `tmp_path` still shows it, which proves it is in the event log. The model's next request contains
   `Changed: …`.
4. **Decline.** `resume=[cancelled]` leaves the facts unchanged, and the model is told `Declined by the user.`
5. **No resume entry.** A write call without a matching resolved entry is declined and never runs.
6. **One parametrized test per write tool, checked through the REST reads:**
   - `add_fact`: an achievement under a position, and a skill (Person found).
   - `edit_fact`: the summary on the Person; also, attribute keys not mentioned are kept.
   - `delete_fact`: the position's achievements go too.
   - `merge_facts`, then `undo_merge`: `list_merges` shows the pair, then not.
   - `add_link` / `remove_link`: through `GET /api/graph`.
   - `remove_source`: through `GET /api/sources`.
7. **Failures.**
   - An unknown fact id or bad arguments gives `Failed: …` in the tool result and a 200 stream, not a 500.
   - `add_fact` on an empty career fails cleanly.
8. **No model.** With no connection, the stream has `RUN_ERROR` with the Settings text.
9. **The stream is AG-UI.** Every SSE `data:` line validates against the `ag_ui.core` event models. This is the event
   schema check.

### Property tests: `tests/test_chat_tools_props.py` (Hypothesis)

- For any current attributes and changes, `edit_fact` keeps every key not in the changes, sets the changed ones, and
  removes keys with empty values. This is checked through `POST /api/chat` with an approved resume, or through
  `ChatTools.run` as the module's public entry point.
- AG-UI message to LangChain message and back keeps role, content, tool-call ids and arguments.

### Mutation testing

`mutmut` targets `application/chat_tools.py`, with a goal of at least 80% killed. Add it to `[tool.mutmut]` paths.

### BDD

Add the story `docs/project/user_stories/accepted/career-chat.md` with the Gherkin scenarios 1 to 4 and 6 above. Gap:
`pytest-bdd` is not a dependency yet and `accepted/` is empty. The scenarios are implemented as the plain pytest tests
above, named after each scenario, in line with current repo practice.

### Frontend: `frontend/src/components/chat/ChatSidebar.test.tsx` (vitest + testing-library)

`fetch` is mocked to return the recorded SSE fixture `frontend/src/test/fixtures/chat-*.sse`, captured from the backend
test in Phase 0. The fixture is the contract between the two sides.

1. A user message shows the assistant's reply text.
2. A read tool call renders a tool card with the tool name and a one-line result.
3. A write proposal renders the approval card with the describe text and Apply and Decline buttons, and the composer is
   disabled.
4. Apply sends a second request whose body has `resume[0].status === "resolved"`, the card shows `Changed: …`, and
   `['facts']` is invalidated (`queryClient` spy).
5. Decline sends `"cancelled"`.
6. `RUN_ERROR` shows the Settings notice.

### Manual check list

- [ ] With a real model connected, "What did I do at <employer>?" answers from `find_facts` and `get_fact`, and no
      approval card appears.
- [ ] "Add an achievement to <position>: cut build time by 40%" shows a card with that exact text. After Apply, the
      career screen shows it without a reload.
- [ ] "Change my summary to …" shows the before and after. Decline leaves it unchanged.
- [ ] "Merge these two skills", then "undo that", works, and the duplicates banner updates.
- [ ] "Link <skill> to <position>", then the graph view shows the edge. Unlink removes it.
- [ ] "Remove source cv.pdf" says what is hidden. After Apply, the Sources screen updates.
- [ ] "Delete <position>" says its achievements go too and that it cannot be undone.
- [ ] With no model connected, the sidebar shows the Settings notice.
- [ ] In the dev server (Vite proxy), text arrives without a long stall, so SSE is not buffered.

## Files

All files stay under 400 lines, the `spec-ops health` warning line.

| File | Change | Lines (est.) |
|---|---|---|
| `pyproject.toml`, `uv.lock` | `uv add ag-ui-protocol` (1.0.x), then `uv lock` and `uv lock --check` | n/a |
| `src/career_buddy/application/chat_tools.py` | **new**: argument models, the `TOOLS` table (name, description, write flag), and `ChatTools(edits, queries, projector, on_source_removed)` with `run`, `describe`, `context` | ~250 |
| `src/career_buddy/application/services.py` | `CareerQueries.merges()` over `Projector.absorbed()` | +12 (to ~376) |
| `src/career_buddy/adapters/inference/chat_graph.py` | **new**: `GraphCareerChat(chat)` with `.run(input, tools) -> AsyncIterator[BaseEvent]`, AG-UI to LangChain message conversion, resume handling, and the 2-node `StateGraph` streamed with `astream(stream_mode="updates")` | ~170 |
| `src/career_buddy/adapters/inference/prompts/career_chat_v1.txt` | **new**: the system prompt (rules, how to use the tools, write only what the user said) | ~40 |
| `src/career_buddy/adapters/inference/errors.py` | Move `_unavailable` here from `writer_graph.py` and import it in both | +12 |
| `src/career_buddy/adapters/inference/connections.py` | `Inference.chat`; build `chat_model` once and share it | +4 |
| `src/career_buddy/composition.py` | `App.chat_tools`; `current("chat")` | +5 |
| `src/career_buddy/web/chat_routes.py` | **new**: `chat_router(chat, tools)`: `POST /api/chat` that takes `RunAgentInput` and returns `StreamingResponse` with `EventEncoder` | ~45 |
| `src/career_buddy/web/app.py` | `include_router(chat_router(...))`, passing `source_log.drop` | +2 |
| `tests/test_chat_api.py` | **new** | ~300 |
| `tests/test_chat_tools_props.py` | **new** | ~80 |
| `frontend/package.json`, lockfile | Exact pins: `@assistant-ui/react`, `@assistant-ui/react-ag-ui`, `@ag-ui/client` (^1.0.3 per the assistant-ui docs, pinned exact), each at least two weeks old | n/a |
| `frontend/src/api/endpoints.ts` | `chat: () => '/api/chat'` | +1 |
| `frontend/src/components/chat/ChatSidebar.tsx` | **new**: runtime provider, thread, composer (primitives styled with Chakra via `asChild`), and the invalidate-on-finish effect | ~170 |
| `frontend/src/components/chat/ToolCards.tsx` | **new**: the `ToolCard` fallback for every tool call and the `ApprovalCard` built on `useAgUiInterrupts` and `useAgUiSubmitInterruptResponses` | ~110 |
| `frontend/src/components/chat/ChatSidebar.test.tsx` and `frontend/src/test/fixtures/chat-*.sse` | **new** | ~160 |
| `frontend/src/app/AppShell.tsx`, `frontend/src/app/SidebarNav.tsx` | Place the panel beside `ActivitySidebar` (reusing `useResizableWidth`); add a Chat toggle button next to `LogsButton` | +10 |
| `docs/reference/career-chat-tools.md` | **new**: the tool table and the approval rule (Diataxis reference) | ~50 |
| `docs/project/adrs/accepted/adr-0010-career-chat-ag-ui.md` | **new**: LangGraph loop, AG-UI on the wire, approvals as interrupts, stateless runs | ~50 |
| `docs/project/user_stories/accepted/career-chat.md` | **new**: the story with Gherkin | ~60 |

There are no new domain events and no new REST routes besides `/api/chat`.

## Phases

Each phase leaves `uv run pytest`, `npm test`, `npm run typecheck`, `uv run spec-ops health` and `uv lock --check`
green.

### Phase 0: spike (about half a day; throwaway except the fixture and the dependencies)

1. `uv add ag-ui-protocol`, then check the 4 unverified items above:
   - `RunFinishedEvent(outcome=...)` builds and encodes.
   - Install the npm packages.
   - Render the primitives and a Fallback inside `ChakraProvider` in vitest.
   - Drive `HttpAgent` against a stub SSE stream and assert the second run's `messages` carries the tool results.
2. Record the SSE fixture.
3. Decide between interrupts and `pendingToolCallIds` (see the fallback above).

### Phase 1: read-only chat (the first shippable slice)

- `/api/chat` with the loop and the 5 read tools, plus the context.
- The sidebar with text and tool cards.
- The no-model notice.
- Backend tests 1, 8 and 9; frontend tests 1, 2 and 6.
- Built with five read tools (phase 1): `find_facts`, `get_position` (with its achievements), `list_skills`, `list_sources`, `get_relationships`. `list_duplicates` and `list_merges` were not built.
- The sidebar is global, beside `ActivitySidebar`, opened by a Chat button next to Logs; it does not resize.

### Phase 2: approved fact edits

- `add_fact`, `edit_fact` (including the summary) and `delete_fact`.
- The interrupt and resume path, the approval card, and the invalidate-on-finish effect.
- Backend tests 2 to 7 for these tools; frontend tests 3 to 5; property tests; mutmut.
- The ADR, the story and the reference doc.

Built (phase 2):

- `ChatTools(queries, edits)` gains `describe` (the exact change in words, or `Failed: ...`), `apply` (runs it through `EditService`, answers `Changed: ...`) and
  refuses write names in `run`. `delete_fact` says "cannot be undone" but not how many facts go with it; the cascade count was not built.
- `chat_graph.py`: the tools node answers reads, and for each write collects an interrupt (no tool message). When there are any, the run ends with
  `RUN_FINISHED` `outcome` interrupt. `settle()` rebuilds the transcript on the next run: a write call in the last assistant message runs only when its
  `resume` entry is `resolved` with `approved: true`; every other open write call is `Declined by the user.`
- Frontend: `ToolCard` is the approval card too (Apply and Decline call `respondToApproval`); the composer is disabled while an interrupt is open;
  `ChatSidebar` invalidates `facts`, `graph`, `duplicates` and `sources` whenever a run finishes (the plan's single effect, so a read-only run also refetches).
- Tests: `tests/test_chat_writes.py` and `frontend/src/components/chat/ChatApproval.test.tsx`. The approval card test reuses the phase-0 interrupt fixtures.
- Not done in this phase (still listed above): the property tests, mutmut, the ADR, the BDD story and `docs/reference/career-chat-tools.md`
  (the tool table lives in `docs/reference/chat-api.md`).

### Phase 3: merges, relationships, sources

- `merge_facts`, `undo_merge`, `add_link`, `remove_link`, `remove_source`, and `CareerQueries.merges()`.
- The remaining parametrized tests; the manual check list.

### Phase 4: optional token streaming

Map LangGraph `stream_mode="messages"` chunks to `TEXT_MESSAGE_CONTENT` deltas. Only do this if waiting for whole
replies feels slow.

## Open questions

1. **Keep the chat after a reload?** Default: **no**. The thread lives in memory for the tab. Saving it later would
   use assistant-ui's history adapter and a small JSON file, and needs no server-side session.
2. **Approve each change separately, or with one "Apply all" button when the model proposes several?** Default:
   **one card per change**, each with Apply and Decline. The run resumes once every card is answered, because AG-UI
   needs an answer for each open interrupt.
3. **Stream tokens in the first slice?** Default: **no**. Whole replies per model step, with token streaming as
   Phase 4.

## Sources

- assistant-ui AG-UI runtime: https://www.assistant-ui.com/docs/runtimes/ag-ui/overview and
  https://www.assistant-ui.com/docs/runtimes/ag-ui/runtime-options
- AG-UI Python types: https://docs.ag-ui.com/sdk/python/core/types
- `ag-ui-protocol` on PyPI: https://pypi.org/project/ag-ui-protocol/
- The `ag-ui-langgraph` checkpointer requirement:
  https://docs.langchain.com/oss/langchain/frontend/integrations/copilotkit
