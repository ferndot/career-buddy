# ADR-0009: The document writer is a tool-calling model on LangGraph

## Status
Accepted (narrows ADR-0008 item 2: "No LangChain" no longer holds for the document writer; extraction, rewriting and job review keep redstring's `LlmProvider`)

## Context
The writer asked redstring's `extract` for one JSON object and parsed it from free text. Checks (`validated`, `ground`) ran afterwards, and one separate repair call fixed rejected slots. The schema was only requested in words, and a revision was a different prompt and a different output shape.

## Decision
1. The writer calls one tool, `submit_document`, whose arguments are `WrittenDocument`. The provider enforces the schema (`tool_choice` forces the tool).
2. The checks stay in the application (`DocumentGeneration.generate`, passed to the writer as `accept`). After each submit their result goes back to the model as the tool's reply; the model submits once more. At most 2 model calls per document (`domain/coverage.MAX_REVISIONS`).
3. A revision changes only the slots that were rejected (`domain.written.merged`); accepted text is never rewritten.
4. The loop is a small LangGraph graph (`adapters/inference/writer_graph.py`): model, check, and a conditional edge from the pure `domain.coverage.next_step`. No checkpointer.
5. Client: `langchain-openai` `ChatOpenAI` for every preset, Anthropic's included (its OpenAI-compatible endpoint). `langchain-anthropic` takes no injected httpx client or transport (checked), which the offline tests and the no-redirect rule need. The OpenAI client is given the existing `openai_client`, so base URL, key header and test transport are the same as before.
6. The JSON writer, its repair call and prompt v7 are removed; the prompt is `document_writer_v8.txt`.

## Consequences
- A model without tool calling cannot write documents: the person gets "Check that it can call tools". The other steps are unaffected.
- Dependencies added: `langgraph`, `langchain-core`, `langchain-openai`.
- Not verified here: a live model call. The tests use an `httpx.MockTransport` that answers in the OpenAI tool-call shape, plus a scripted fake chat model for the loop bound.
- Length and coverage checks (phase 2 of `docs/project/plans/langgraph-writer.md`) are not built yet.
