# Chat API

The career chat answers questions about the career facts and, with the person's approval, adds, edits and deletes facts, merges and unmerges them, links and unlinks them, and removes sources. It needs a connected model
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

| `list_merges` | none | `[{canonical: {id, title}, alias: {id, title}}]`: each merge that can be undone, automatic merges included |

Hidden facts are not shown. The model also starts from a short context: the person's name and summary, the number of facts of each kind, and each position
with its id (at most 30).

### Write tools

| Tool | Arguments | Change |
|---|---|---|
| `add_fact` | `kind` (`Position`, `Achievement`, `Skill` or `Education`), `title`, `parent_id` (the position's id for an achievement; the others go under the person), `attributes` | Adds the fact. A position's `description` is dropped, so nothing is read into achievements that nobody approved |
| `edit_fact` | `fact_id`, `title` (optional), `changes` (attributes to set; an empty value removes one; the others stay) | Revises the fact. The summary is `edit_fact` on the person with `changes: {"summary": "..."}` |
| `delete_fact` | `fact_id` | Deletes the fact for good |
| `merge_facts` | `canonical_id`, `alias_ids` (one or more) | Merges facts of one kind into the kept fact; the others are shown as it. The card lists the kept fact and each fact merged into it. A merge of several is checked whole first, so it is never half done |
| `unmerge_fact` | `alias_id`, `canonical_id` (as `list_merges` shows them) | Undoes that merge |
| `add_relationship` | `source_id`, `target_id`, `kind` (`AT`, `ATTENDED`, `USES_SKILL` or `ACHIEVED`) | Links two facts, for example a position `ACHIEVED` an achievement or a position `USES_SKILL` a skill. Only the kinds the career screen lets you edit, between the kinds it allows |
| `remove_relationship` | `source_id`, `target_id`, `kind` | Removes that link |
| `remove_source` | `source` (as `list_sources` shows it) | Removes the source; the card says how many facts it gave. Facts that only it stated are hidden |

All of them go through `EditService`, so each change is an event in the log, the same as an edit on the career screen. The tool descriptions tell the model to write
only what the person said or confirmed. A call that cannot be made (unknown id, kinds that do not match, nothing to change, a link already there or not there,
a merge that was not made, an unknown source) answers `Failed: <the reason>` at once and shows no approval card. Reading relationships stays with
`get_relationships`.

A card with several lines (a merge) keeps its line breaks:

```
Merge into Skill 'Python' (kept):
- 'Py'
- 'Pyton'
They are shown as 'Python' from now on. This can be undone.
```

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
