---
title: career-buddy v2 plan
status: Shaped
created: 2026-11-14
extends: prd-0001
---

# career-buddy v2 plan

## Goals

1. Import PDF and DOCX resumes.
2. Edit facts through a fixed-template form editor.
3. Templates for every output: resumes, letters, and others.
4. Tailor any output to a job posting without inventing facts.
5. ATS-compatible output, proven by an automated round-trip check.
6. No AI text markers in outputs.
7. A simple frontend: three steps, few controls.

## Key decisions

| # | Decision | Why |
|---|---|---|
| D1 | **PDF output uses ReportLab (BSD), not WeasyPrint.** | WeasyPrint 70 has a hard dependency on Pyphen, licensed GPL-2.0+/LGPL-2.1+/MPL-1.1 (checked on PyPI). It also needs Pango and GLib, which are LGPL. xhtml2pdf needs svglib (LGPL-3.0+). ReportLab 5.1 depends only on pillow and charset-normalizer. |
| D2 | **Templates are data, not text templates.** One pure `Document` model, and one renderer per format. No Jinja2. | ReportLab and python-docx cannot use HTML templates. One model gives one ATS-safe structure in all five formats. |
| D3 | **Form-based editor in vanilla JS. No Tiptap.** | The data is structured facts, not rich text. ATS output allows almost no inline formatting. Tiptap would add an npm build step. |
| D4 | **Tailoring is deterministic: select and reorder.** Rewording is optional, comes from an LLM, is verified, and the user accepts or rejects each change. | It is explainable and testable, and it cannot invent facts. |
| D5 | **AI markers: strip safe swaps automatically, flag ambiguous words, never change stored facts.** | See "AI-marker policy". |
| D6 | **Reuse the import readers for the ATS check.** | The pdfminer and python-docx readers built for import also extract our own output back. |
| D7 | ~~Drop redstring.~~ **Superseded by ADR-0008: redstring is reintroduced for extraction and the graph store.** | See "Graph store decision". |

## Graph store decision (D7)

The app calls only `upsert_entities`, `find_entities`, `upsert_relationships` and `get_relationships`. The graph is a projection rebuilt from `events.jsonl` at every start, so the store needs no persistence and no graph algorithms. It only needs adjacency lookups by link kind.

| Option | License | Gives | Costs | Verdict |
|---|---|---|---|---|
| redstring 0.13 | MIT | `Consolidator` for entity merging | 13 transitive packages used nowhere else (sqlalchemy, dateparser, regex [Apache-2.0 AND CNRI-Python], eventsource-py...). Heavy entity, tenant and provenance model. Young API (0.x). Requires Python >=3.13. Its merge engine (blocking, embeddings, graph scores) is sized for large multi-tenant graphs, not one person's career. | Drop |
| networkx | BSD-3 | Graph algorithms | Nothing here needs algorithms. | Not needed |
| rustworkx | Apache-2.0 | Fast algorithms | Same as networkx, plus native wheels | Not needed |
| **Plain in-memory store** | none | `dict[id, Fact]` plus a set of links, about 40 lines | None | **Choose** |
| rapidfuzz | MIT | Fast fuzzy scores | One dependency. A career has fewer than 100 organizations, so speed does not matter. | Upgrade path |
| **difflib (stdlib)** plus suffix normalization | PSF (stdlib) | Ratio scores | Slower, which is irrelevant at this scale | **Choose** |

**Dedup design (`domain/dedup.py`, about 80 lines, pure):**

1. Normalize organization names: lowercase, strip punctuation, drop legal suffixes (inc, corp, corporation, co, ltd, llc, plc, gmbh, sa, ag). "Acme" and "Acme Corp." then match exactly.
2. Otherwise `difflib.SequenceMatcher(...).ratio()` >= 0.90 makes a pair a candidate.
3. Positions become candidates when the normalized title is the same, the organization is the same or merged, and the dates overlap.
4. Nothing is merged automatically. The editor shows "Acme and Acme Corp look like the same employer. Merge?", and the user confirms.

**How to swap later:**

- **Store.** `FactGraph` is the seam and `composition.py` is the only place that picks the adapter. Write `NetworkxFactGraph` (or reinstate redstring) with the same `apply` and `snapshot` methods and change one line. The event log is the truth and is never migrated. The existing HTTP test suite is the contract test for any adapter.
- **Fuzzy matching.** All fuzzy scoring sits in one function in `domain/dedup.py`. Swapping in `rapidfuzz.fuzz.token_sort_ratio(a, b) / 100` is a one-line change.

## Architecture changes

Layers stay the same. Each file stays under 500 lines (estimates below are in lines).

### Domain (pure)

| File | Contents | Est. |
|---|---|---|
| `domain/document.py` | `Document`, `Section`, `Entry`, `Line(text, source_fact_id, origin)`. `origin` is one of `fact`, `user`, `suggestion`, `boilerplate`. | 90 |
| `domain/templates.py` | `TemplateSpec` (sections, heading labels, caps, required inputs), the registry, and `build_document(profile, spec, selection, inputs)` | 250 |
| `domain/tailoring.py` | Job terms, scoring, `select`, `verify_rewording`. Absorbs `rank_for_job`. | 220 |
| `domain/markers.py` | Marker lists as data, `scan`, `clean(text, origin) -> (text, changes)` | 150 |
| `domain/ats.py` | `check(expected: Document, extracted: Extracted) -> list[Issue]` | 140 |
| `domain/dedup.py` | `merge_candidates(batch) -> list[(a, b, score)]` | 80 |
| `domain/events.py` | Adds `FactRevised` and `FactsMerged` | +20 |
| `domain/profile.py` | Views gain an `id`. Achievements become `(id, text)`. Hidden facts are filtered out. | +30 |

### Ports (`application/ports.py`)

- `TextReader.read(bytes) -> Extracted(text, lines, has_tables, has_text_boxes, header_footer_text, image_count)`. It serves import and the ATS check.
- `DocumentRenderer`: `format`, `media_type`, `render(doc, style) -> bytes`. It replaces `ResumeRenderer` and `CoverLetterWriter`.
- `Rewriter.suggest(lines, job_terms, banned) -> list[Suggestion]` (optional).
- `EventLog` is widened to `Event = FactsImported | FactRevised | FactsMerged`.
- `FactGraph` is unchanged.
- Markers, tailoring and dedup get no port. They are pure functions.

### Adapters

| Adapter | Library | Notes |
|---|---|---|
| `graph/memory_graph.py` | none | Replaces `redstring_graph.py`, which is deleted |
| `readers/pdf_text.py` | pdfminer.six | `LAParams(boxes_flow=0.5)`, `maxpages=10`, reports images. Raises `NoTextLayer` when there is no text. |
| `readers/docx_text.py` | python-docx + lxml | Reads body, tables, `w:txbxContent` and headers/footers. Checks the zip's uncompressed size before opening. |
| `outputs/render_{markdown,html,text}.py` | stdlib | HTML via `html.escape` |
| `outputs/render_docx.py` | python-docx | Built-in styles (`Title`, `Heading 1`, `List Bullet`). No tables or text boxes. Empty header and footer. |
| `outputs/render_pdf.py` | reportlab | One `Frame`, Helvetica or Times, Letter or A4 |
| `inference/openai_rewriter.py` | httpx | Same configuration as the extractor |
| `storage/jsonl_event_log.py` | none | Dispatches on `type`. Unknown types are skipped with a warning. |

The old `resume_*.py` and `cover_letter_template.py` are deleted once the new renderers produce the same Markdown.

### Application

- `projector.py`: one `project(event)` path for live commands and for replay at startup. It keeps `revisions` and `merges` (alias to canonical).
  - A revision beats a later re-import of the same id.
  - A merge rewires the alias's links to the canonical fact and hides the alias.
- `documents.py`: `preview`, `render`, `check`, `suggest`.
- `services.py`: imports, queries, `revise`, `add_fact`, `merge`.

## Data model and events

- **Unchanged:** `FactsImported {type, facts, links}`. Existing `data/events.jsonl` replays as it does today.
- **New:** `{"type": "FactRevised", "fact_id", "title", "attributes", "at"}`. `attributes` is a full replacement for that fact.
- **New:** `{"type": "FactsMerged", "alias_id", "canonical_id", "at", "undo": false}`. Undo is the same event with `undo: true`.
- **Hide** = `FactRevised` with `attributes.hidden = "true"`. Nothing is ever deleted.
- **Manual add** = `FactsImported` with `source: "manual"`.
- **Bullet order** = `attributes.order`.
- Fact ids stay the UUIDv5 from first import. A revised title keeps its id.
- **Compatibility:** v2 reads v1 logs. A v1 binary cannot read a v2 log (documented). `tests/fixtures/events-v1.jsonl` locks the behavior.
- Tailored drafts live in browser `localStorage`, not on the server (open question 8).

## Tailoring

1. **Job terms:** tokens and bigrams minus stopwords. Weight goes up for terms that are frequent, capitalized or tech-shaped, or that appear in "requirements" lines.
2. **Score:** each achievement scores the matched weights over its text, its position's title, and its linked skills.
3. **Select** (caps come from the template):
   - All positions are kept in reverse chronological order. Positions are never reordered or dropped.
   - Bullets are sorted by score, ties broken by original order. Keep the top *k* (classic 5, compact 3), at least 1 per position.
   - Skills: matched skills first, in job order, then by how many positions use them. Cap at 15 or 10.
   - Summary: the stored summary verbatim, or none. Never made up.
4. **Report:** matched terms, plus missing terms the user may add **if true**. They are never added automatically.
5. **Optional LLM rewording.** `verify_rewording` rejects a candidate that:
   - contains a number not in the source;
   - contains a skill or proper noun not in the source or the profile's skills;
   - contains a banned marker;
   - is more than 1.3 times the source length;
   - changes a title, organization, date or degree.

   Survivors are shown as diffs. The user accepts or rejects each one.
6. **Invariant (Hypothesis):** every rendered line has a `source_fact_id`, or `origin` is `boilerplate` or `user`.
7. **Without an LLM,** tailoring is selection and ordering only. Letters are slot templates filled from the top facts. LLM polish is optional and goes through the same verifier.

## AI-marker policy (resolving "strip" vs "flag")

The user's request wins for **output**. The research advice wins for **stored facts** and ambiguous words. Cleaning runs at render time.

| Class | Examples | User or imported text | LLM text |
|---|---|---|---|
| Artifacts (cleanup, not authorship evidence) | zero-width chars, "As an AI language model", "Certainly! Here's", stray `**` | strip | strip |
| Weak signal: swaps | delve into to explore, in the realm of to in (user text); also showcasing to showing, underscores to highlights, tapestry to mix (LLM text only, flagged in user text) | replace or flag, as listed | replace |
| Weak signal: ambiguous | intricate, potential, findings | flag only | flag only (no reject, no regeneration) |
| Weak signal: em dash | em dash | flag only | replace with ", " |

Sources: Kobak et al. 2025 (arXiv 2406.07016), Liang et al. 2024 (arXiv 2404.01268), Wikipedia "Signs of AI writing". Words with no source (critical, utilize, landscape, leverage, "in today's fast-paced world") are not listed. The preview labels every non-strip change "weak signal".

The preview lists every change and every flag, and each swap can be undone per word.

## ATS compliance

### By construction

1. Single column. No tables, text boxes, columns, images or icons.
2. Name on line 1 and contact info on line 2, in the body. Header and footer stay empty.
3. Fixed headings: Summary, Experience, Education, Skills, Certifications.
4. Fonts: DOCX uses Calibri, Arial, Georgia or Times New Roman at 10-12 pt. PDF uses Helvetica or Times.
5. Title, organization and dates on one line. Dates as `Mon YYYY - Mon YYYY` or `- Present`.
6. Bullets use DOCX `List Bullet` or a plain bullet character.
7. Margins of at least 0.5 in. Letter or A4.
8. File name `First-Last-Resume.docx`.
9. No emoji or zero-width characters. PDF text limited to WinAnsi.

### Automated check (`POST /api/documents/check`)

Render, read back with the same `TextReader`, then `domain/ats.check`:

- Expected lines appear in order, with coverage of at least 98%.
- The name is in the first 2 lines, and the headings are in template order.
- DOCX has no `w:tbl`, `w:txbxContent`, `w:drawing` or `w:pict`, and no header/footer text.
- PDF has 0 images, a text layer on every page, and no unmapped glyphs.
- Re-importing the extracted text with `HeuristicExtractor` recovers the same position titles and organizations.

The badge says "Passes ATS check", never "certified".

## Template set

| Kind | Id | Required inputs |
|---|---|---|
| Resume | `resume-classic` (default, reverse-chronological) | none |
| Resume | `resume-compact` (one-page target) | none |
| Resume | `resume-hybrid` (skills first, for career changers) | none |
| Letter | `cover-letter` | company, role; recipient optional |
| Letter | `cover-letter-email` | company, role |

Every template renders to DOCX, PDF, TXT, MD and HTML. Functional resumes are left out on purpose.

## Editor UI

Three steps across the top: **Import, Edit, Create**.

- **Import:** one drop zone (PDF, DOCX, ZIP, CSV, TXT, MD) plus "paste text instead". After import, the page goes straight to Edit.
- **Edit:**
  - Header card.
  - Experience cards: title, organization, dates, and bullets (one input each, with up, down and remove), plus "+ bullet".
  - Education cards and a skills field.
  - Autosave on blur. Delete hides the fact and shows an Undo toast.
  - A "Possible duplicates" banner with Merge and Not the same.
- **Create:**
  - Pick a type, then a template, then optionally paste a job posting.
  - Preview on the right. On the left: bullet checkboxes, matched and missing chips, marker changes, and suggestions (only with an LLM).
  - Downloads: DOCX, PDF and TXT, with MD and HTML under "More". ATS badge alongside.
- **Implementation:** split into `index.html`, `app.css`, `import.js`, `edit.js`, `create.js`. No build step.

## HTTP API (new)

| Endpoint | Purpose |
|---|---|
| `POST /api/import/file` | PDF, DOCX, TXT or MD to facts. 413 over 10 MB. 415 unknown type. 422 bad file or no text layer. |
| `GET /api/profile` | Nested profile with ids |
| `PATCH /api/facts/{id}` and `POST /api/facts` | Revise, and manual add |
| `GET /api/duplicates` and `POST /api/merges` | Merge candidates, and confirm or undo a merge |
| `GET /api/templates` | Templates and required inputs |
| `POST /api/documents/{preview,render,check,suggest}` | `{template, format?, job_text?, inputs, selection?, overrides?}` |

`/api/resume/{fmt}` and `/api/fit` stay as aliases. `create_app` gains an optional `llm_client` parameter for HTTP tests that use `MockTransport`.

## Phases (ordered by risk; each one ships)

### Phase 1: Document model, renderers, ATS gate, graph swap (highest risk: the PDF engine)

- Build `resume-classic`, five renderers, both readers and `ats.check`. Replace redstring with `memory_graph.py`.
- **Accept when:**
  - DOCX and PDF downloads work.
  - `check` passes in every format.
  - Old endpoints return identical Markdown.
  - All 8 existing tests pass on the new store.
  - `uv.lock` loses the 14 packages listed under "Removed".
- **Tests:**
  - HTTP render per format.
  - pdfminer and python-docx inspections.
  - A unit test where `ats.check` fails on an interleaved two-column extraction.

### Phase 2: PDF and DOCX import (high risk: real-world resume variety)

- `/api/import/file`, limits, new bullet glyphs, and an "Org / Title / dates on separate lines" heuristic.
- **Accept when:** a two-column PDF imports without interleaving, and DOCX text boxes, tables and header contact info are all imported.
- **Tests:** fixtures generated in the tests (a ReportLab two-frame PDF, a python-docx file with a table, a text box and a header), a scanned (image-only) PDF, and an oversized upload.

### Phase 3: Editing and duplicate merging

- `FactRevised`, `FactsMerged`, the projector, `dedup.py`, and the Import and Edit steps of the UI.
- **Accept when:**
  - The v1 log replays.
  - An edit survives a restart and a re-import.
  - Resume text "Acme Corp" plus PDF "Acme" are proposed as one employer, and after the merge the resume shows one employer.
  - Undo restores both.
- **Tests:**
  - HTTP tests.
  - Hypothesis: candidates are symmetric with no self-pairs; replay of revisions is order-independent.
  - One Playwright journey.

### Phase 4: Tailoring and markers

- **Accept when:**
  - Bullets reorder toward the job, and missing terms are reported, never added.
  - `/api/facts` is unchanged by rendering.
  - "delve into" is swapped, "critical" is flagged and kept, and zero-width characters are stripped.
  - A mocked suggestion with a new number is rejected.
- **Tests:** HTTP tests with `MockTransport`; Hypothesis checks that `clean` is idempotent and leaves digits unchanged, and that every line has a source.

### Phase 5: Full template set and the Create step

- **Accept when:** every template passes `check` in every format (parametrized matrix), and a missing required input returns 422.
- **Tests:** matrix tests over HTTP and a Playwright journey from template to tailored PDF.

## Risks and open questions (recommended default in bold)

1. **PDF engine:** WeasyPrint is excluded by license. ReportLab gives no tagged PDF. **Default: ReportLab. HTML stays available for the browser's "Print to PDF".**
2. **Strip vs flag:** **Default: the marker table above.**
3. **Em dashes:** **Default: flag in user text, replace in LLM text.**
4. **Pillow (MIT-CMU) and typing_extensions (PSF-2.0)** are permissive but not on the named list. **Default: accept both.**
5. **Hypothesis (MPL-2.0)** is required by AGENTS.md. **Default: dev-only, never shipped.**
6. **Non-Latin names in PDF:** **Default: the ATS check fails with a message. Bundle DejaVu Sans only if you need it.**
7. **Playwright in CI:** **Default: Chromium only, one journey per UI phase.**
8. **Server-side drafts:** **Default: no. Use `localStorage`. Add a `DocumentSaved` event later if wanted.**
9. **Paper size:** **Default: Letter, A4 as an option.**
10. **OCR for scanned PDFs:** **Default: out of scope, return 422.**
11. **Heuristic quality on real PDFs:** **Default: recommend the LLM extractor. Please provide 2-3 anonymized resumes as fixtures.**
12. **ATS rules are blog-sourced:** **Default: "passes our ATS check", never "certified".**
13. **Old positions:** **Default: keep all. The compact template trims their bullets.**
14. **Dropping redstring loses a future upgrade path to its LLM and embedding consolidation.** **Default: drop it now. Reinstate it through the `FactGraph` port if dedup ever needs embeddings.**
15. **Auto-merge exact normalized matches?** **Default: no. Always ask, because a wrong merge corrupts the resume.**

## Dependencies

| Package | License | Role | Pulls in |
|---|---|---|---|
| pdfminer.six | MIT | PDF text | charset-normalizer (MIT), cryptography (Apache-2.0 OR BSD-3), cffi (MIT), pycparser (BSD-3) |
| python-docx | MIT | DOCX read and write | lxml (BSD-3), typing_extensions (PSF-2.0, already locked) |
| reportlab | BSD | PDF output | pillow (MIT-CMU), charset-normalizer |
| hypothesis (dev) | MPL-2.0 | property tests | none |
| pytest-playwright, playwright (dev) | Apache-2.0 | e2e | Chromium (BSD) |

**Removed:** redstring and the 13 packages only it uses: eventsource-py, sqlalchemy, greenlet, orjson, opentelemetry-api, dateparser, regex, python-dateutil, pytz, tzlocal, tzdata, jellyfish, pyyaml.

**Rejected:**

- WeasyPrint: Pyphen is GPL/LGPL/MPL, and Pango is LGPL.
- xhtml2pdf: svglib is LGPL-3.0+.
- fpdf2: LGPL-3.0.
- PyMuPDF: AGPL.
- Tiptap: wrong shape for this app. (GrapesJS, BSD-3, was accepted later for the Edit step, vendored and locked to ATS-safe blocks.)
- Jinja2: not needed.
- networkx, rustworkx, rapidfuzz: not needed yet (see D7).
