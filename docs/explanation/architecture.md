# Architecture

career-buddy uses ports and adapters, with writes and reads split (CQRS). Layers depend inward only: adapters know the application layer, the application layer knows the domain, and the domain knows nothing else.

```
src/career_buddy/
  domain/          pure: Fact/Link model, profile assembly, Document model, templates, tailoring,
                   grounding, ATS check, events
  application/     ports (protocols) and services: import, queries, documents, saved documents, generation
  adapters/
    sources/       job link fetcher
    inference/     heuristic extractor, OpenAI-compatible and Anthropic clients, document writer,
                   job reviewer, LLM connections
    storage/       JSONL event log (append-only, the source of truth), key store (OS keychain or a
                   private file), local and S3 object stores (original uploads and saved documents)
    graph/         redstring in-memory graph store, a projection of the log
    consolidation/ duplicate-skill candidates (redstring)
    outputs/       Markdown, HTML, TXT, DOCX (python-docx) and PDF (Playwright) renderers
    readers/       PDF (pdfminer.six), DOCX (python-docx), Markdown, TXT and HTML text readers
    jobs/          in-memory import job state and the per-source log
  web/             FastAPI HTTP adapter. It also serves the React UI.
  composition.py   the only place that picks concrete adapters
frontend/          React UI (Vite, Chakra UI). It is built into src/career_buddy/web/static.
```

## How data flows

A write appends a `FactsImported` event to the log, then projects it into the graph. On startup the graph is rebuilt by replaying the log. The log is the truth and the graph is derived.

Facts get deterministic IDs (UUIDv5 over kind, title and scope), so importing the same data again does not duplicate it.

## How documents are written

A document is built from every visible fact. The model is sent those facts and writes text for the summary, bullets, skills or letter paragraphs. Each text must cite facts it was sent and may not add claims the facts do not make. Texts that fail are sent back once for repair, and a text that still fails is flagged for the user. See the [Documents API](../reference/documents-api.md) for the exact rules.

Every rendered file is read back with the same readers that serve import, and an ATS check reports problems. The check is a warning and never blocks a download.

## Add a source or an output

Write one adapter that implements a port in `application/ports.py`, then wire it in `composition.py`.

## Rules

- Source files stay under 500 lines. See [Contributing](../contributing.md).
- Tests go through public entry points such as the HTTP API, not private internals.
- Specifications, stories, tasks and decisions live in `docs/project/` and follow [SpecOps](https://github.com/sanmak/specops)-style project management as code. See [Project management as code](project-management-as-code.md).

## Limits

- The ATS check is our own round trip, not a test against real applicant tracking systems.
- The offline reader has not been measured on a set of real resumes.
