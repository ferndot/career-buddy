# Saved documents API

A saved document is a rendered file plus a small record, kept in the object store (an S3 server with `CAREER_BUDDY_STORAGE=s3`, such as SeaweedFS,
otherwise `<data dir>/objects`). Keys are `documents/<id>/file.<ext>` and `documents/<id>/meta.json`. The `id` is 32 lowercase
hex characters; any other id answers `404`.

| Endpoint | Purpose |
|---|---|
| `GET /api/saved-documents` | List of records, newest first |
| `POST /api/saved-documents` | Render and save. `201` with the record |
| `GET /api/saved-documents/{id}/file` | The file, with `Content-Disposition: attachment` and its stored media type. `404` unknown |
| `DELETE /api/saved-documents/{id}` | Remove the record and the file. `204`; `404` unknown |

A record is `{id, label, template, format, filename, created_at, ats_issues}`. `created_at` is ISO 8601 in UTC.
`ats_issues` lists the codes of the ATS checks that failed when the file was saved (see [Documents API](documents-api.md)).

`POST` takes the same body as `POST /api/documents/render`
(`template`, `format`, `job_text`, `inputs`, `selection`, `skill_ids`, `education_ids`, `overrides`, `font`, `paper`)
plus `label` (default empty: the record's label is the file name without its extension). An unknown template or format
answers `404`; a format that cannot run here, such as PDF without Chromium, answers `503`. Missing required inputs answer `422`.

## Choosing skills and education

`skill_ids` and `education_ids` (also accepted by preview, check, render and suggest) pick facts by id, as `selection` does for
bullets. Take the ids from `GET /api/profile` (`skill_ids` is parallel to `skills`; each `education` entry has an `id`).
`null` or omitted keeps the default, a list keeps exactly those entries (no cap), and `[]` keeps none.
