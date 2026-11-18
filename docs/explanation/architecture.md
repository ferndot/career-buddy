# Architecture

career-buddy uses ports and adapters, with writes and reads split (CQRS). Layers depend inward only: adapters know the application layer, the application layer knows the domain, and the domain knows nothing else.

```
src/career_buddy/
  domain/          pure: Fact/Link model, profile assembly, Document model, templates, tailoring,
                   written document, grounding, ATS check, events
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

A document is written by the model, not filled from fixed slots. It is sent, in its first message, the context: every visible fact (positions with dates, achievements, skills, education), the job posting and the reviewed role and company, the person's directions, and system instructions for the document kind, general resume or letter rules (`domain/writing_rules.py`, plain data that a person's own set can replace), the template (its own instructions and its section list) and the resume length. It answers with the whole document: the template's sections in order, each a list of items. It chooses the wording, which facts to use how many bullets each position gets (and, for several positions at one company, whether to condense them under one item or keep them apart), and a cover letter is one block of paragraphs. Each text cites the facts it rests on (`domain/written.py` is the schema and the rules that make the answer fit to print). Every text must cite facts it was sent and may not add claims the facts do not make (`domain/grounding.py`); the writer is a tool-calling model (`adapters/inference/writer_graph.py`, a small LangGraph graph): it submits the document by calling one tool, the checks run in code, and texts that fail go back as the tool's reply for one revision of those texts only, and a text that still fails is flagged for the user. A saved document keeps the sections as its layout, the model's text, and the person's own words keyed by slot id (`bullet:<first cited fact id>`, `summary`, `para:<n>`), so an edit survives a regenerate. See the [Documents API](../reference/documents-api.md) for the exact rules and an [example of the model's input](../reference/example-writer-input-modern.md).

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
