# Sources API

`GET /api/sources` lists every source:

```json
[{"source": "ada.txt", "facts": 4, "status": "ready", "progress": 100, "step": "Done", "error": null}]
```

- `status`: `queued`, `processing`, `ready` or `failed`. `progress` is 0-100. `step` is a short label. `error` is set only when failed.
- With a model connection active, `POST /api/import/text` and `POST /api/import/file` answer `202` with that record and finish in the background; poll `GET /api/sources`. With the offline reader they finish first and answer `200 {"facts": n}`.
- `POST /api/sources/{source}/reindex` reads the stored original again, extracts with the active connection (or the offline reader) and replaces that source's facts. `202` with the record; `404` unknown source; `409` already processing; `422` no stored original (a LinkedIn export).
- `DELETE /api/sources/{source}` answers `409` while the source is processing.
- Processing state is held in memory: after a restart every source reads as `ready`.
- CORS: origins from `CAREER_BUDDY_CORS_ORIGINS` (comma-separated, default `http://localhost:5173,http://127.0.0.1:5173`).

## Processing log

`GET /api/sources/{source}/log?since=<cursor>` returns what the work on that source logged, for the live log on the Sources screen:

```json
{"lines": [{"seq": 7, "time": "2026-01-01T10:00:00+00:00", "level": "INFO", "logger": "career_buddy.extraction.pipeline", "message": "chunk 1: asking the model about 900 characters"}],
 "cursor": 7, "run": 1, "status": "processing", "progress": 30, "step": "Extracting positions", "error": null}
```

- Send the returned `cursor` as `since` on the next poll to get only newer lines (start with `0`). The screen polls every second while the source is queued or processing.
- `run` counts the runs of that source. When it changes, discard the lines you hold: a new run replaced the log.
- Each source keeps the last 500 lines of its latest run, in memory (lost on restart, dropped when the source is removed). `404` for an unknown source.
- Lines are the `career_buddy` loggers' INFO and above, filed under the source being processed. `CAREER_BUDDY_LOG_LEVEL` (see the app's logging setup) decides what is logged at all.
