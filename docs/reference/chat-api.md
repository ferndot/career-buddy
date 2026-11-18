# Chat API

The career chat answers questions about the career facts. It is read-only: it cannot change any data. It needs a connected model
(see [Connect a model](../how-to/connect-a-model.md)).

`POST /api/chat` takes an [AG-UI](https://docs.ag-ui.com) `RunAgentInput` (JSON, camelCase: `threadId`, `runId`, `state`, `messages`, `tools`, `context`,
`forwardedProps`) and answers an event stream (`text/event-stream`, one `data:` line per AG-UI event). The server keeps no history: each request carries the
whole thread in `messages` (user messages, assistant messages with their `toolCalls`, and `tool` messages with the result).

The events of a run: `RUN_STARTED`; for each model reply `TEXT_MESSAGE_START/CONTENT/END` (the whole text in one `CONTENT` event) and
`TOOL_CALL_START/ARGS/END` for each call; `TOOL_CALL_RESULT` for each tool that ran; then `RUN_FINISHED`. A run that fails ends with `RUN_ERROR` instead (the
HTTP status is still 200): `code: "no_model"` with the text "Connect a model in Settings to chat about your career." when no model is connected, or
the model server's status code. A run stops after 12 steps of the loop, with a short text answer.

## Tools

The tools run in the server and answer in JSON text. A bad argument or an unknown id answers `Failed: ...` and the run goes on.

| Tool | Arguments | Answers |
|---|---|---|
| `find_facts` | `query` (words in the title or attributes, may be empty), `kind` (optional) | `{total, facts}`: at most 25 facts, each `{id, kind, title, attributes, source}` |
| `get_position` | `fact_id` | The position, its organization and its achievements |
| `list_skills` | none | `{total, skills}`: `{id, title}` for each skill (at most 200) |
| `list_sources` | none | `{source, facts, status}` for each source |
| `get_relationships` | `fact_id` | The fact and each link: `{kind, direction, other_id, other_title, other_kind}` |

Hidden facts are not shown. The model also starts from a short context: the person's name and summary, the number of facts of each kind, and each position
with its id (at most 30).
