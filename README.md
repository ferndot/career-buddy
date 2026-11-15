# career-graph

Import your career data (LinkedIn export, resume text), keep it as a graph of facts
(positions, achievements, skills, education), and generate resumes and cover letters from that graph.

## Run it

### With Docker (easiest)

Requires Docker. Chromium for PDF output is already in the image.

```bash
docker compose up --build
```

Open http://127.0.0.1:8080. Your data lives in `./data` on the host, so it survives rebuilds. Port 8080 is
used because 8000 is often taken; change it in `docker-compose.yml`.

To use a model, add a connection in Settings (see [LLM connections](#llm-connections)). In the container, `localhost` is
the container itself, so reach Ollama or LM Studio on your computer at `http://host.docker.internal:11434/v1` (Ollama) or `:1234` (LM Studio).

### Without Docker

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 for you).

```bash
uv sync
uv run career-graph
```

PDF output prints a page with Chromium through [Playwright](https://playwright.dev/python/). Install the browser once
(about 150 MB, stored outside the project):

```bash
uv run playwright install chromium
```

Without it everything else works. A PDF request returns HTTP 503 with this instruction, and the PDF tests are
skipped with the same message.

Open http://127.0.0.1:8000 (or the port set by `PORT`). Data is stored in `./data/events.jsonl` (override with `CAREER_GRAPH_DATA`).

## LLM connections

Without a model, the offline heuristic reads your resume. To use a model, open **Settings > LLM connections**, add one,
press **Test** (it asks the server for its model list: no resume text is sent and it costs nothing), then **Set active**.
Only one connection is active at a time, or none.

| Provider | Address | Key |
|---|---|---|
| Anthropic | `https://api.anthropic.com/v1` (fixed, native Messages API) | required |
| Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai` (fixed) | required |
| Ollama | `http://localhost:11434/v1` | none |
| LM Studio | `http://localhost:1234/v1` | none |
| llama.cpp | `http://localhost:9931/v1` (its Docker image uses 8080) | optional |
| Custom URL | any OpenAI-compatible server | optional |

- **Where keys go:** the OS keychain (via `keyring`). With no keychain, or with `CAREER_GRAPH_KEY_STORE=file` (the Docker
  image sets it), keys go to `secrets.json` in the data folder, mode 0600 but plain text. Settings (without keys) are in
  `llm-settings.json`. The page and API only ever show a masked key such as `sk-...a1f2`, and keys are never logged.
- **Changing an address removes its saved key**, so a key cannot be sent to a new host. Cloud addresses cannot be edited.
- **Private addresses** (such as `192.168.x.x`) show a warning and must be confirmed. Link-local and metadata addresses are refused.
- **Environment variables still work.** `CAREER_GRAPH_LLM_BASE_URL`, `CAREER_GRAPH_LLM_MODEL` and `CAREER_GRAPH_LLM_API_KEY`
  show up as a read-only "From environment variables" connection, active until you choose another or turn it off.
- **Local use only:** requests with another `Host` header are refused. Add names in `CAREER_GRAPH_ALLOWED_HOSTS` (comma separated) if you put it behind a proxy.
- **Live tests** (`tests/test_llm_live.py`) only list models, and run when `CAREER_GRAPH_LIVE_ANTHROPIC_KEY` or `CAREER_GRAPH_LIVE_GEMINI_KEY` is set.

API: `GET /api/llm/providers`, `GET|POST /api/llm/connections`, `PATCH|DELETE /api/llm/connections/{id}`, `PUT /api/llm/active`, `POST /api/llm/test`.

## Storage for uploaded originals

`POST /api/import/file` keeps the original bytes as `sources/<sha256>.<ext>` and records that key in the import event
(`source_key` in `events.jsonl`). The same file is stored once. Choose where with `CAREER_GRAPH_STORAGE`:

- `local` (default): files under `${CAREER_GRAPH_DATA}/objects`.
- `s3`: any S3 API, built for [MinIO](https://min.io) run as a separate container (reached over the S3 API only).
  Set `CAREER_GRAPH_S3_ENDPOINT`, `CAREER_GRAPH_S3_BUCKET`, `CAREER_GRAPH_S3_ACCESS_KEY`, `CAREER_GRAPH_S3_SECRET_KEY`
  and optionally `CAREER_GRAPH_S3_REGION` (default `us-east-1`). The bucket is created on startup if missing.

To run an S3 server next to the app, use the optional `storage` compose profile. It starts
[SeaweedFS](https://github.com/seaweedfs/seaweedfs) (Apache-2.0, pinned to `chrislusf/seaweedfs:4.51`) as a separate,
unmodified container, because MinIO no longer publishes community images. Plain `docker compose up` is unchanged.

```bash
# .env next to docker-compose.yml (the defaults are dev-only placeholders)
CAREER_GRAPH_STORAGE=s3
CAREER_GRAPH_S3_ACCESS_KEY=pick-a-key
CAREER_GRAPH_S3_SECRET_KEY=pick-a-long-secret
```

```bash
docker compose --profile storage up --build
```

The app reaches the server at `http://s3:8333` (bucket `careers`); the S3 API is also on `127.0.0.1:8333` for the
integration test. Objects live in the `s3-data` Docker volume, not in `./data`. To use your own MinIO or another S3
instead, leave the profile off and set `CAREER_GRAPH_S3_ENDPOINT`.

`tests/test_s3_minio_integration.py` runs against a real S3 server (MinIO, SeaweedFS, ...) when `CAREER_GRAPH_S3_ENDPOINT` and the other `S3` variables are set; otherwise it is skipped.

## Import sources

- **LinkedIn**: request your data export from LinkedIn (Settings → Data privacy → Get a copy of your data), then upload the ZIP or the individual CSVs (`Profile.csv`, `Positions.csv`, `Skills.csv`, `Education.csv`).
- **Resume text**: paste plain text or Markdown. Headings such as *Experience*, *Skills* and *Education* help the heuristic extractor. Position lines look like `Title at Organization, 2019 - 2023`, or three lines in a row: organization, title, dates. Bullets can be `-`, `*`, `•`, `●`, `▪`, `■` or `◦`.

- **Resume file**: `POST /api/import/file` takes a PDF, DOCX, TXT or MD (up to 10 MB). It reads the text, then extracts facts the same way as pasted text. Errors: 413 over 10 MB, 415 unknown type, 422 for a corrupt file or a PDF with no text layer (scans need OCR, which is not supported). Two-column PDFs are read column by column. DOCX tables, text boxes and the header (contact info) are included.

## Output

`POST /api/documents/render` and `POST /api/documents/check` take `{"template": "resume-classic", "format": "docx", "font": "sans", "paper": "letter"}`.
Formats: `markdown`, `html`, `txt`, `docx`, `pdf`. `check` renders the file, reads it back with the same text readers that
will serve import, and reports ATS problems (reading order, coverage, name position, heading order, tables, text boxes,
header text, images, missing text layer). `/api/resume/markdown` and `/api/resume/html` still work.

## Architecture

Ports and adapters, with CQRS split between writes and reads. Layers depend inward only.

```
src/career_graph/
  domain/          pure: Fact/Link model, profile assembly, Document model, templates, ATS check, events
  application/     ports (protocols) and services: ImportService, CareerQueries, DocumentService
  adapters/
    sources/       LinkedInExportParser             (structured export -> facts)
    inference/     HeuristicExtractor, OpenAICompatibleExtractor, AnthropicExtractor  (text -> facts), LLMConnections
    storage/       JsonlEventLog                    (append-only event log, the source of truth)
                   KeyStore                         (API keys: OS keychain, or a private file)
                   LocalObjectStore, S3ObjectStore  (original uploads; boto3 against MinIO or any S3)
    graph/         MemoryFactGraph                  (plain in-memory projection)
    outputs/       Markdown, HTML, TXT, DOCX (python-docx), PDF (Playwright) renderers
    readers/       PDF (pdfminer.six), DOCX (python-docx), Markdown/TXT/HTML text readers
  web/             FastAPI HTTP adapter and a static single-page UI
  composition.py   the only place that picks concrete adapters
```

Writes append a `FactsImported` event to the log, then project it into the graph. On startup the
graph is rebuilt by replaying the log, so the log is the truth and the graph is derived. Facts get
deterministic IDs (UUIDv5 over kind, title and scope), so re-importing the same data does not duplicate it.

Adding a source or an output means writing one adapter that implements a port in
`application/ports.py` and wiring it in `composition.py`.

## Develop

```bash
uv run pytest
```

Tests drive the HTTP API end to end, plus a few pure-domain unit tests. The development process
follows [SpecOps](https://github.com/sanmak/specops)-style specs under `docs/project/`.

## Limits and next steps

- Facts can be edited, added, reordered and merged (`PATCH /api/facts/{id}`, `POST /api/facts`, `GET /api/duplicates`,
  `POST /api/merges`); the full template list is at `GET /api/templates` (see `docs/project/product/plan-v2.md`).
- The ATS check is our own round trip, not a test against real applicant tracking systems.
- The heuristic extractor has not been measured on a set of real resumes yet.
- The LinkedIn CSV headers follow the export format as I know it. Verify them against your own export.

## License

Apache-2.0. See [LICENSE](LICENSE). Dependencies are permissive: FastAPI (MIT), uvicorn (BSD),
httpx (BSD), keyring (MIT), python-multipart (Apache-2.0), Playwright (Apache-2.0), pdfminer.six (MIT), python-docx (MIT), boto3 (Apache-2.0). The S3 server (SeaweedFS in the `storage` profile, or your own MinIO) is not a dependency; it runs apart and is reached over the S3 API.
