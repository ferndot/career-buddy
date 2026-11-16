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
- CORS: origins from `CAREER_GRAPH_CORS_ORIGINS` (comma-separated, default `http://localhost:5173,http://127.0.0.1:5173`).
