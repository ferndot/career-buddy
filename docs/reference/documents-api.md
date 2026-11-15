# Documents API

All document endpoints take `{template, format?, job_text?, inputs?, selection?, overrides?}`.

| Endpoint | Purpose |
|---|---|
| `GET /api/templates` | `[{id, kind, label, formats, required, optional}]` for the eight templates |
| `POST /api/documents/render` | The file, with `Content-Disposition`. `format` is `docx`, `pdf`, `txt`, `markdown` or `html` |
| `POST /api/documents/preview` | `{lines, document, tailoring, markers, ats}`. `ats` checks `format` (default `docx`) |
| `POST /api/documents/check` | `{passes, issues}` for one format |

Templates: `resume-classic`, `resume-compact`, `resume-hybrid`, `cover-letter` (company, role), `cover-letter-email`
(company, role), `thank-you` (company, role, interviewer, interview_date), `follow-up` (company, role, applied_date),
`linkedin-about`. A missing or blank required input returns 422 and names it. Unknown inputs are ignored.

## ATS check is a warning

Every render and preview reads the file back and runs `domain/ats.check`. A failing check never blocks the download.
`render` adds `X-ATS-Issues: code,code` (absent when the check passes). The codes are `coverage`, `order`, `name`,
`headings`, `table`, `text_box`, `header_footer`, `images`, `text_layer` and `glyphs`.

## Editor

The Edit step is a GrapesJS canvas (vendored in `web/static/vendor/grapesjs`, no CDN) locked to five block types:
section card, heading, paragraph, bullet list and list item. Text is edited in place and saved on blur with
`PATCH /api/facts/{id}`. `gjs.js` removes anything else added to the canvas, pastes plain text only, and ignores Enter
and drops. The block types are tested in Chromium (`tests/test_e2e_blocks.py`).
