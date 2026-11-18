# Chat API

The career chat answers questions about the career facts and, with the person's approval, adds, edits and deletes facts. It needs a connected model
(see [Connect a model](../how-to/connect-a-model.md)).

`POST /api/chat` takes an [AG-UI](https://docs.ag-ui.com) `RunAgentInput` (JSON, camelCase: `threadId`, `runId`, `state`, `messages`, `tools`, `context`,
`forwardedProps`) and answers an event stream (`text/event-stream`, one `data:` line per AG-UI event). The server keeps no history: each request carries the
whole thread in `messages` (user messages, assistant messages with their `toolCalls`, and `tool` messages with the result).

The events of a run: `RUN_STARTED`; for each model reply `TEXT_MESSAGE_START/CONTENT/END` (the whole text in one `CONTENT` event) and
`TOOL_CALL_START/ARGS/END` for each call; `TOOL_CALL_RESULT` for each tool that ran; then `RUN_FINISHED`. A run that proposes a change ends with an interrupt (see Approved changes). A run that fails ends with `RUN_ERROR` instead (the
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

### Write tools

| Tool | Arguments | Change |
|---|---|---|
| `add_fact` | `kind` (`Position`, `Achievement`, `Skill` or `Education`), `title`, `parent_id` (the position's id for an achievement; the others go under the person), `attributes` | Adds the fact. A position's `description` is dropped, so nothing is read into achievements that nobody approved |
| `edit_fact` | `fact_id`, `title` (optional), `changes` (attributes to set; an empty value removes one; the others stay) | Revises the fact. The summary is `edit_fact` on the person with `changes: {"summary": "..."}` |
| `delete_fact` | `fact_id` | Deletes the fact for good |

All three go through `EditService`, so each change is an event in the log, the same as an edit on the career screen. The tool descriptions tell the model to write
only what the person said or confirmed. A call that cannot be made (unknown id, missing parent, no person yet, nothing to change) answers `Failed: ...` at once
and shows no approval card.

## Approved changes

A write tool never runs in the run that proposes it. The run ends with `RUN_FINISHED` whose `outcome` is
`{"type": "interrupt", "interrupts": [{"id": <tool call id>, "reason": "tool_call", "toolCallId": <tool call id>, "message": <the exact change in words>}]}`,
one interrupt per proposed write. assistant-ui shows each as a tool call waiting for approval, with `message` as the prompt, for example
`Position 'Senior Engineer': title 'Senior Engineer' -> 'Staff Engineer'; started '2019-03' -> '2018-03'`.

The person's answer starts the next run: the same transcript (the assistant message with the open tool call, no `tool` message for it yet) plus
`resume: [{"interruptId": <id>, "status": "resolved", "payload": {"approved": true | false}}]`, one entry per interrupt. The server runs a write only when its
entry is `resolved` with `payload.approved` exactly `true`, and the call is in the last assistant message. Every other open write call (a decline, `cancelled`,
no entry, an entry for another id) is answered `Declined by the user.` and changes nothing. A run's `TOOL_CALL_RESULT` for an applied write is
`Changed: <the same words>`. The model sees these answers as the tool results.

The chat sidebar then refetches the career queries (`facts`, `graph`, `duplicates`, `sources`), so the career screen shows the change without a reload.
