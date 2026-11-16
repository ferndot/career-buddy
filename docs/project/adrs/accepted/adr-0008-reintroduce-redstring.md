# ADR-0008: Reintroduce redstring as the extraction and graph-store engine

## Status
Accepted (supersedes decision D7 in `docs/project/product/plan-v2.md`)

## Context
D7 dropped redstring 0.13 because of 13 transitive packages, a heavy tenant and provenance model, a young 0.x API, and a merge engine sized for large multi-tenant graphs. Since then the owner decided the career graph should lean on redstring for LLM extraction and graph storage, and accepted the dependency weight.

redstring (`tyevans/redstring`, MIT, Python 3.13+) depends on `eventsource-py` (MIT) as a core dependency. Its exported types need it, so it is installed with redstring.

## Decision
1. Add `redstring` as a runtime dependency (pinned by `uv.lock`).
2. LLM extraction goes through redstring's `ExtractionPipeline`, behind the existing `FactExtractor` port. A career domain schema (YAML) supplies the prompt and asks for positions named 'Title at Organization', so the same title at two employers stays apart. A provider adapter speaks the OpenAI-compatible chat API over httpx. No LangChain. Anthropic connections keep their native API path.
3. The fact graph is stored in redstring's `InMemoryGraphStore`, behind the existing `FactGraph` port. `MemoryFactGraph` is removed.
4. The event log stays the source of truth (`events.jsonl`, unchanged). The projector keeps its overlays (revisions, merges, dismissals, removed sources). Imports still append a `FactsImported` event holding the mapped `FactBatch`, so no new event type is needed for extraction.
5. Duplicate suggestions for skills use redstring's `CandidateFinder` (`adapters/consolidation`). Organizations and positions still use the difflib rules in `domain/dedup.py`. Suggestions only: a merge still needs the user's `FactsMerged` event.
6. Redstring's `Consolidator` auto-merge is not used. Its undo is session-only without an eventsource store, and a wrong automatic merge would silently hide a real job.

## Consequences
- Positive: extraction, candidate scoring and the graph store come from a maintained library.
- Still open: the TypeScript profile assembly (`model.ts`) duplicates the Python one; its removal needs a backend profile endpoint.
- Negative: 13+ transitive packages return; redstring is pre-1.0 and its API may move. The `uv.lock` pin and the `redstring` version range are the guard.
- Not done: an eventsource `AggregateStore` over the JSONL log (needed only if Consolidator undo must survive restarts).
- Known shortcuts: the graph store records every fact as a pattern-derived claim (provenance does not keep the LLM/structured split). Skill matching uses redstring's `redstring.domain.blocking` and `CandidateFinder`, which are internal dotted imports and may move in a 0.x release; the version is pinned to `>=0.13,<0.14`.
