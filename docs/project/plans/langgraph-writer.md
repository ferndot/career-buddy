---
title: Resume writer as one tool-calling model on LangGraph
status: Proposed
date: 2026-11-17
target_bc: generation (application/generation.py, domain/written.py, domain/grounding.py, new domain/coverage.py)
depends_on: resume-length change (Default or 1-page), in flight
---

# Resume writer as one tool-calling model on LangGraph

## Problem

`DocumentGeneration.generate` (application/generation.py) makes one `DocumentWriter.write` call through
`ProviderDocumentWriter` (adapters/inference/document_writer.py). That call asks redstring's `LlmProvider.extract` for one
JSON object (`StructuredOpenAIProvider` / `StructuredAnthropicProvider`, parsed by `read_reply` in structured.py). Then:

- `validated()` (domain/written.py) normalises the answer.
- `ground()` (domain/grounding.py) checks each claim.
- `_repaired` makes one `repair` call for the slots that failed.

Resumes come out sparse and relevant roles get dropped:

- `_experience` in written.py cuts every position to `caps.bullets` (3 at 1 page, 5 at Default). This is a guess at page
  length, applied the same way to every role whatever its relevance.
- `RESUME_RULES[3]` and the v7 `### resume` section invite leaving roles out.
- Nothing checks coverage or the real length. A resume that drops three roles, or runs onto a second page at "1 page",
  passes.

The fix that changes output:

- Remove the per-position caps.
- Measure the rendered page count of the whole document.
- Check that relevant roles are present.
- Feed both into one revise round, and let the writer split the space by relevance.

The writer moves to a tool-calling chat model on LangGraph. The JSON-extraction writer is removed.

## Are tool calls overengineering?

Not with one tool. All facts for one resume fit in the first message, so read tools would add round trips and no
information. A check the model may choose to skip would sometimes not run. So:

- **One tool, `submit_document`**, whose argument schema is `WrittenDocument`. `tool_choice` forces it on every call. It
  replaces "reply with JSON matching this schema" and `read_reply`'s brace-hunting, because the provider enforces the
  schema.
- **The check is the tool's result, not a tool.** After each submit, code merges, validates, grounds, renders and counts
  pages, and checks coverage. It returns the failures as the `ToolMessage`, and the model submits once more in the same
  conversation.
- **No read tool.** Every achievement is in the first user message and stays in the history.

## Chat model client

`adapters/inference/chat_models.py` (new, ~40 lines) holds `chat_model(conn, key, transport) -> BaseChatModel`. It is
called from `LLMConnections.inference()` beside `_client`, with the same connection, key, `check_url`'d base URL and test
transport:

- **`anthropic` preset:** `ChatAnthropic(model=conn.model, api_key=key, base_url=conn.base_url, max_tokens=4096)`. Phase 1
  first verifies that langchain-anthropic accepts an injected httpx client or transport. It is needed for `MockTransport`
  tests and to keep redirects off. If it does not, use `ChatOpenAI` on Anthropic's OpenAI-compatible endpoint and drop the
  dependency.
- **Every other preset:** `ChatOpenAI(model=conn.model, base_url=conn.base_url, api_key=key or "none", temperature=0,
  http_async_client=openai_client(conn.base_url, key or "", transport), max_retries=0)`.

`Inference.writer` becomes `GraphDocumentWriter(chat_model(...))`. The extractor, rewriter and reviewer keep redstring's
`LlmProvider` unchanged.

## Ports

In `application/ports.py`:

```python
class DocumentWriter(Protocol):
    async def write(self, brief: Brief, accept: Accept) -> Checked: ...

class PageCounter(Protocol):
    def pages(self, doc: Document, style: Style) -> Pages: ...   # RendererUnavailable when Chromium is missing
```

- `Accept = Callable[[Checked | None, WrittenDocument], Awaitable[Checked]]` is passed in by the application. It merges,
  validates, grounds, measures and checks coverage, so the adapter holds no rules.
- `Checked(doc, kept, rejected, pages, issues)` is a frozen dataclass in domain/coverage.py.
- `repair` is deleted.
- No langchain type crosses a port.

## Measuring pages

`adapters/outputs/page_count.py` (new, ~40 lines) holds `PdfPageCounter`:

1. It renders with the existing `PdfRenderer.render(doc, style)`. That is the same `html_page` + Chromium `page.pdf` path
   that the saved document's PDF export prints, with the same paper and 0.75in margins. `html_page` and the saved HTML
   (`stored_html`) both take their CSS from `document_css(style, layout)` (adapters/outputs/render_html.py), so the template
   layout is measured. DOCX pagination (`DEFAULT_FORMAT = "docx"`) is not measured and can differ in Word.
2. It reads the bytes with pdfminer, which is already a dependency (`PdfTextReader`).
3. It returns `Pages(count, last_fill, lines_per_page)`:
   - `last_fill` is the lowest text line's position on the last page, as a share of the printable height.
   - `lines_per_page` is the number of text lines on page 1.

How generate gets there:

- `generate` builds the `Document` with `DocumentService.compose(template, options, written=doc)`, the same
  `to_document` path that a saved document uses.
- It runs the counter in `asyncio.to_thread`, as `DocumentService._file` does.
- `generate` gains `style: Style = Style()`. `SavedDocuments.regenerate` passes `Style(c.meta.font, c.meta.paper)`.

Overflow is `count - limit - 1 + last_fill` pages, where the limit is 1, or 2 at Default. The report turns it into lines:
`overflow × lines_per_page`.

**Cost.** One Chromium launch plus a print, about 0.5 to 1.5 s, runs once per submit. That is at most 2 per generate,
against model calls of 10 to 60 s. Resumes only. When Chromium is missing (`RendererUnavailable`), the length check is
skipped, `pages` is null, and generation still works.

> shortcut: pinned slots are blank in the draft, so their text is not measured. Upgrade by composing with the saved
> overrides if pinned text often causes overflow.

## Graph

New file `adapters/inference/writer_graph.py` holds `GraphDocumentWriter`.

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    checked: Checked | None   # the current accepted document
    rounds: int               # revise rounds done
    failed: bool              # the model did not answer a revise call
```

| Node | Does |
|---|---|
| `model` | `await chat.bind_tools([WrittenDocument], tool_choice="submit_document").ainvoke(messages)`. If the provider fails or no tool call comes back, round 0 raises `LLMUnavailable` and later rounds set `failed`. |
| `check` | Parses the tool args as `WrittenDocument` (invalid args count as a failed round), sets `checked = await accept(checked, doc)`, and appends `ToolMessage(report(checked))`. Increments `rounds` after a revise. |

Edges:

- `START -> model -> check`.
- `add_conditional_edges("check", route, {"revise": "model", "end": END})`. `route` calls the pure
  `coverage.next_step(rounds, checked, failed)`.

`next_step` ends when any of these holds:

- nothing is left to fix;
- `rounds >= MAX_REVISIONS` (1), so there are at most 2 model calls;
- `failed`.

The graph uses `compile()` with no checkpointer, and `recursion_limit=6` as a backstop only.

**The report** lists:

- each rejected slot with its reasons;
- each missing relevant role, with its achievement ids;
- the length, for example "renders 1 page + 30% of page 2, limit 1 page: cut about 14 lines. Remove or shorten the least
  relevant bullets; keep every relevant role." On a 1-page resume that fills under 75% of the page while relevant
  achievements are unused, it says "room for about N lines".

**Revise rules** are applied in code by `merged(brief, previous, submitted, over)` in written.py:

- A rejected slot takes the submitted text.
- New items or bullets are appended.
- An accepted slot keeps its text, whatever the model resends.
- An accepted slot the model omits is removed only when `over` (the previous render exceeded the limit). Otherwise it is
  kept.
- Pinned slots are never removed.

Removing a slot never adds ungrounded text. Shortening comes from replacing a rejected slot or removing one.

**Source of truth:** `generate` grounds the returned document once more. `MAX_REJECTED`, `UngroundedDraft` and `final()`
are unchanged. Letters use the same graph without measurement or coverage, so only rejections are revised.

**Still over after the revise:** the draft is returned as written, with `Draft.json()["pages"] = {"count", "limit"}` so
the person sees it. There is no automatic code trim.

## Coverage check

New file `domain/coverage.py`, pure and a mutmut target.

`relevant_positions(brief)` counts a position as relevant when either:

- it matches a `brief.terms` term (the matching in domain/tailoring.py), or
- it finished within 15 years (domain/dates.py). An unparseable date counts as recent.

`issues(brief, doc, pages, limit)` returns:

- `missing_position` for a relevant role that has no item and is not in an `also` group;
- `room_left` (1 page only): `last_fill < 0.75` and relevant achievements are unused;
- `too_long`: the page count is over the limit.

It also holds `next_step` and `MAX_REVISIONS = 1`.

There are no per-role targets. The prompt tells the writer to give space by relevance.

**Caps:**

- `Caps` keeps `pages` and `skills` and loses `bullets`.
- `_experience` no longer slices bullets.
- `system_prompt` drops "At most N bullets for each position".
- `RESUME_RULES[3]` becomes "give the most space to the most relevant roles; condense older ones, do not drop relevant
  ones".

## Files (all under 400 lines)

| File | Change | Est. lines |
|---|---|---|
| `adapters/inference/chat_models.py` | new: `chat_model` | ~40 |
| `adapters/inference/writer_graph.py` | new: `State`, nodes, `GraphDocumentWriter`, plus `system_prompt`, `payload` and `report` (the first two moved from document_writer.py) | ~180 |
| `adapters/inference/prompts/document_writer_v8.txt` | v7 with output wording for the tool, `### revise` instead of `### repair`, and relevance and length wording | ~45 |
| `adapters/outputs/page_count.py` | new: `PdfPageCounter` | ~40 |
| `domain/coverage.py` | new: `Checked`, `Pages`, `Issue`, `issues`, `next_step` | ~110 |
| `adapters/inference/document_writer.py`, `prompts/document_writer_v7.txt` | deleted | - |
| `adapters/inference/connections.py` | `inference()` builds the chat model and the writer | +6 |
| `application/ports.py` | `DocumentWriter`, `Accept`, `PageCounter`; `repair` removed | ±15 |
| `application/generation.py` | `_accept` (merge, validate, ground, measure, issues); `style` arg; `pages` on `Draft`; `_repaired` removed | ~150 |
| `application/saved_documents.py`, `web/document_routes.py`, `web/requests.py` | pass the style; optional `style` on the generate request model in requests.py | +5 |
| `composition.py`, `web/app.py` | `DocumentGeneration(..., pages=PdfPageCounter())`; a `page_counter=None` seam through `create_app` and `build_app`, like `llm_transport` | +6 |
| `domain/written.py` (246), `domain/generation.py`, `domain/writing_rules.py` | `merged`; caps cut removed; `Caps.bullets` removed; rule wording | ±40 |
| `tests/test_generate_api.py` (437) | the `Model` fake answers with tool calls | ±40 |
| `tests/test_coverage.py` | new: coverage, `merged`, `next_step`, Hypothesis | ~170 |
| `tests/test_writer_graph.py` | new: loop-bound property test with a fake chat model | ~90 |
| ADR (next in REGISTRY.md), `docs/explanation/architecture.md`, `docs/reference/example-writer-input-modern.md` | decision, sketch, payload | - |

## Tests

**Through `POST` generate** (ADR-0003). The `Model` fake stays an `httpx.MockTransport` behind `connect_mock`. It now
replies with `tool_calls` (`submit_document`, JSON arguments) and treats a last message with `role: "tool"` as a revise.
That makes it a fake tool-calling chat model at the HTTP boundary, and it also exercises `ChatOpenAI`.

- Most cases pass a fixed `page_counter` through the composition seam, so they need no Chromium.
- Cases:
  - a missing relevant role is reported and added;
  - an over-length report removes omitted bullets and keeps the accepted text of the rest;
  - a revise that is not over length cannot drop bullets;
  - an invented number in an addition is flagged;
  - a revise that answers 500 keeps the first draft;
  - never more than 2 calls;
  - pinned slots survive;
  - no tool call returns 503.
- One `chromium`-fixture test (tests/conftest.py) uses the real counter. A long 1-page resume reports `too_long` with a
  line estimate, and the returned `pages.count` matches the PDF export.

**Hypothesis:**

- `next_step` ends whenever `rounds >= 1` or `failed`.
- `GraphDocumentWriter.write` runs with a ~25-line `BaseChatModel` test subclass. It answers with random tool calls or no
  tool call, or raises. The writer never makes more than 2 calls and never raises `GraphRecursionError`, and accepted
  slots keep their text.
- `merged` never rewrites an accepted slot, and removes one only when `over`.

**Mutmut:** `domain/coverage.py` and `merged`, at ≥80%.

## Dependencies

`uv add langgraph langchain-core langchain-openai langchain-anthropic`. Run `uv lock --check`.

## Saved documents and frontend

- **Saved documents:** none. Slot ids and `generated.json` are unchanged.
- **Frontend:** small.
  - The generate request may send the chosen `style`; without it, Letter/sans is measured.
  - `Draft.json()` gains `pages: {count, limit} | null`. A one-line notice appears when `count > limit`.

## Phases

1. **Tool-calling writer (first shippable slice).**
   - Add the dependencies, `chat_models.py`, `writer_graph.py`, the new port, `_accept`, `merged` and prompt v8.
   - The single revise covers rejected slots only.
   - Delete the JSON writer and v7, rewrite the `Model` fake, and write the ADR.
   - Verify first: the minimal tool-call reply that langchain-openai and the openai SDK accept from the mock (whether
     `id`, `model` and `object` are required), and the langchain-anthropic transport injection.
2. **Length and coverage.**
   - Add `PdfPageCounter`, the style plumbing, `coverage.py` in the report, `pages` on the draft, the removal of
     `Caps.bullets` and the cut, and the rule wording.
   - Add the tests and run mutmut.

## Cut

- The per-role bullet budget, per-position caps and per-role targets.
- A second revise round and the "issues stopped shrinking" test.
- The offline A/B eval, the model judge and the ship gate.
- The `CAREER_BUDDY_WRITER_LOOP` switch and the parity phase.
- Read tools and a separate check tool.
- An automatic code trim of over-length drafts.
- A reused browser across checks.
- Wrapping `LlmProvider` for the other steps.

## Open questions

1. A model without tool calling gets `LLMUnavailable` ("this model cannot call tools"). Should the Settings connection
   test probe for tool support?
2. **Still over length after the revise?** Recommended: a deterministic trim in phase 2.
   - Drop bullets from roles that are not relevant first, oldest role first.
   - Never drop a pinned bullet or the last bullet of a relevant role.
   - Re-render after each drop, with at most 3 renders (about 3 s).
   - The notice stays for what the trim cannot fix.
   - A 1-page resume printing onto 2 pages is the main failure this plan fixes. If this is accepted, move "automatic
     code trim" out of Cut.
3. Which roles must appear? Proposed: every role that matches the posting or finished within 15 years. Condensing one into
   an `also` group counts.
