---
title: Career chat, phase 0 results
status: Done
date: 2026-11-18
target_bc: web chat route, frontend chat sidebar
depends_on: career-chat.md
---

# Career chat, phase 0: what was checked

Versions: `ag-ui-protocol` 1.0.0 (Python), `@assistant-ui/react` 0.15.32, `@assistant-ui/react-ag-ui` 0.1.1, `@ag-ui/client` 1.0.3 (npm, exact pins; each is at
least two weeks old). The checks that stay as tests are named; the rest were run once.

| # | Unknown | Result | What was seen |
|---|---|---|---|
| 1 | Python `RunFinishedEvent` carries an interrupt outcome | **Pass** | `RunFinishedEvent(outcome=RunFinishedInterruptOutcome(...))` builds and `EventEncoder` writes `"outcome":{"type":"interrupt","interrupts":[{"id","reason":"tool_call","message","toolCallId"}]}`. `RunAgentInput.resume` (a list of `ResumeEntry`) exists too. The stream ends cleanly: `ChatInterrupt.test.tsx` reads a Python-encoded interrupt run and the run settles with one open interrupt. |
| 2 | Tool results return in `RunAgentInput.messages` on the next request | **Pass, with one shape to know** | `ChatSidebar.test.tsx` ("sends the tool call and its result back"): the second request has `user, assistant, tool, user`. The assistant message holds the tool call **and the text that followed it**, because assistant-ui folds one run into one assistant message. The `tool` message carries `toolCallId` and the result. The Python conversion keeps that order (assistant with `tool_calls`, then the tool replies), which the OpenAI API accepts. |
| 3 | A tool-call `Fallback` renders in Chakra under the AG-UI runtime | **Pass** | `ToolCard` is the `tools.Fallback`; it renders inside `ChakraProvider` (`renderApp`) with its Chakra styling, and shows the name, the arguments and the result. The thread, composer and messages are the headless primitives with `asChild`. No style conflict was seen. |
| 4 | The Vite dev proxy streams without buffering | **Pass** | A stub route sent one text message per second. Through `vite` (`/api` proxy) the events arrived one second apart, the same as when read directly from uvicorn. Note for the dev setup: on this Windows machine Vite listens on `localhost` (`::1`), not on `127.0.0.1`, so use `http://localhost:5173`. |

## The interrupt pattern, as it really is (changes to the plan for phases 2 and 3)

The decision is to use assistant-ui's own interrupt and approval support, not a custom mechanism. `ChatInterrupt.test.tsx` shows it end to end.

1. **The interrupt must be a tool-call gate.** assistant-ui turns an interrupt into an approval on the tool call only when it has `reason: "tool_call"`, an
   `id` and a `toolCallId`, and every open interrupt in the run is such a gate. The tool call then arrives at its renderer with
   `approval: { id, prompt }` (`prompt` is the interrupt's `message`), and the renderer calls `respondToApproval({ approved })`. This is the
   "requires approval" state of assistant-ui. No `useAgUiSubmitInterruptResponses` is needed for it; that hook stays for interrupts that are not tool-call gates.
2. **Decline is `resolved`, not `cancelled`.** `respondToApproval({ approved: false })` sends
   `{interruptId, status: "resolved", payload: {approved: false}}`. `cancelled` means the person abandoned the card. The plan's rule "a write runs only on
   `resolved`" is therefore too weak: the server must run a write only when the entry is `resolved` **and** `payload.approved is True`. Any other entry, or none,
   is "Declined by the user.".
3. **The resume request carries the transcript without a result for the open call:** `user, assistant(toolCalls)`. The server rebuilds the run from it, finds the
   open write calls by id in the last assistant message, and runs the approved ones before calling the model.
4. **The batch is all or nothing.** If a run proposes several writes, the card for each is answered, and the run resumes once every interrupt has an
   answer. This matches the plan's default of one card per change.
5. Interrupts are marked experimental in `@assistant-ui/react-ag-ui`. Pins are exact so a change shows up in review.

The fallback in the plan (`pendingToolCallIds`) is not needed.

## Kept from phase 0

- `frontend/src/components/chat/ChatInterrupt.test.tsx`, with the fixtures `chat-interrupt.sse` and `chat-interrupt-resumed.sse` (encoded by the Python SDK).
- The dependencies `ag-ui-protocol`, `@assistant-ui/react`, `@assistant-ui/react-ag-ui`, `@ag-ui/client`.

Not checked: a real browser (only jsdom), and a real model.
