# Saved documents API

A saved document is a small folder in the object store (an S3 server with `CAREER_BUDDY_STORAGE=s3`, such as SeaweedFS,
otherwise `<data dir>/objects`): `documents/<id>/`. The `id` is 32 lowercase hex characters; any other id answers `404`.

A document is kept as restricted HTML, not as a file:

| Key | Content |
|---|---|
| `meta.json` | the record, written last |
| `document.html` | the body, with tags `h1 h2 h3 p ul li` only |
| `document.css` | the layout, from the saved `font` and `paper` |
| `overrides.json` | `{slot id: the user's own wording}`; `{}` when nothing was edited |

Every text line in `document.html` is a slot: `data-slot` (`s1`, `s2`, ...), `data-fact-id` (the fact it was written from),
`data-field` (`title` for a position heading, otherwise `text`) and `data-origin` (`fact`, `user`, `suggestion`, `boilerplate`).
Section titles are fixed headings and have no slot. At download time the HTML is read back into a document; an entry in
`overrides.json` replaces its slot's text, and the line then counts as the user's own. Nothing writes overrides yet.

| Endpoint | Purpose |
|---|---|
| `GET /api/saved-documents` | List of records, newest first |
| `POST /api/saved-documents` | Build and save as HTML. `201` with the record |
| `GET /api/saved-documents/{id}/content` | `{html, css, overrides}`. `404` unknown |
| `GET /api/saved-documents/{id}/file?format=docx\|pdf\|txt` | The file, with `Content-Disposition: attachment`. Default `docx`. `404` unknown; `422` other format; `503` PDF without Chromium |
| `DELETE /api/saved-documents/{id}` | Remove every file. `204`; `404` unknown |

A record is `{id, label, template, filename, created_at, ats_issues}`. `created_at` is ISO 8601 in UTC.
`ats_issues` lists the codes of the ATS checks that failed for the docx at save time (see [Documents API](documents-api.md)).
`filename` has no extension (the download adds one). The download also sends `X-ATS-Issues` (the failed checks for that format)
when there are any.

`POST` takes the body of `POST /api/documents/render` without `format`
(`template`, `job_text`, `inputs`, `selection`, `skill_ids`, `education_ids`, `overrides`, `font`, `paper`)
plus `label` (default empty: the record's label is the file name without its extension). An unknown template answers `404`.
Missing required inputs answer `422`. A `format` field is ignored.

docx and txt are made from the stored HTML and ignore its CSS. PDF is made the same way for now, so it also ignores the CSS.

## Choosing skills and education

`skill_ids` and `education_ids` (also accepted by preview, check, render and suggest) pick facts by id, as `selection` does for
bullets. Take the ids from `GET /api/profile` (`skill_ids` is parallel to `skills`; each `education` entry has an `id`).
`null` or omitted keeps the default, a list keeps exactly those entries (no cap), and `[]` keeps none.
