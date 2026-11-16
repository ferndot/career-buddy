# Documents API

All document endpoints take `{template, format?, job_text?, inputs?, selection?, skill_ids?, education_ids?, overrides?}`.

- `selection`: bullet fact ids to keep. `skill_ids`: skill fact ids to keep. `education_ids`: education fact ids to keep.
  Omitted (or `null`) means the template's own choice: top bullets per position, top skills, all education. A list keeps exactly
  those that exist and ignores the template's caps; an empty list keeps none. Skills keep their job-match order.

To keep a rendered file, see [Saved documents API](saved-documents-api.md).

| Endpoint | Purpose |
|---|---|
| `GET /api/templates` | `[{id, kind, label, formats, required, optional}]` for the five templates |
| `POST /api/documents/render` | The file, with `Content-Disposition`. `format` is `docx`, `pdf`, `txt`, `markdown` or `html` |
| `POST /api/documents/preview` | `{lines, document, tailoring, markers, ats}`. `ats` checks `format` (default `docx`) |
| `POST /api/documents/check` | `{passes, issues}` for one format |

Templates: `resume-classic`, `resume-compact`, `resume-hybrid`, `cover-letter` (company, role), `cover-letter-email`
(company, role). A missing or blank required input returns 422 and names it. Unknown inputs are ignored.

## ATS check is a warning

Every render and preview reads the file back and runs `domain/ats.check`. A failing check never blocks the download.
`render` adds `X-ATS-Issues: code,code` (absent when the check passes). The codes are `coverage`, `order`, `name`,
`headings`, `table`, `text_box`, `header_footer`, `images`, `text_layer` and `glyphs`.
