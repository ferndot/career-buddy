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
| `POST /api/documents/generate` | A draft of the text a document needs, written from the selected facts. See below |

Templates: `resume-classic`, `resume-compact`, `resume-hybrid`, `cover-letter` (company, role), `cover-letter-email`
(company, role). A missing or blank required input returns 422 and names it. Unknown inputs are ignored.

## ATS check is a warning

Every render and preview reads the file back and runs `domain/ats.check`. A failing check never blocks the download.
`render` adds `X-ATS-Issues: code,code` (absent when the check passes). The codes are `coverage`, `order`, `name`,
`headings`, `table`, `text_box`, `header_footer`, `images`, `text_layer` and `glyphs`.

## Generating the text

`POST /api/documents/generate` takes the same body as the other endpoints plus `resume_pages` (`1`, `2` or `3`, default `1`:
how long this resume should be; a letter ignores it; `422` for any other value), `instructions` (free text, at most 2000
characters, `422` over that, empty allowed: the user's direction for tone, length and emphasis) and `pinned` (slot ids the user
wrote themselves; the writer leaves them alone). A letter needs `inputs.company` and `inputs.role` (`422` without). An unknown
template is `404`. Nothing is stored. A model is required: there is no text made without one.

```json
{ "slots": { "summary": "...", "bullet:<id>": "...", "skills": "Python, Go", "para:1": "..." },
  "cites": { "summary": ["<fact id>"] },
  "flags": { "bullet:x": { "code": "not_rewritten", "reasons": ["..."] }, "summary": { "code": "rejected", "reasons": ["..."] } } }
```

- A resume gets `summary`, `bullet:<achievement id>` and `skills`; a letter gets `para:<n>` (a greeting and sign-off are the
  layout's). The ids are the slot ids of [saved documents](saved-documents-api.md). A slot that is absent keeps what the facts say.
- The model is sent every fact the document prints, as `{id, kind, text, position_id, started, finished}`: the summary, each
  position, each ticked achievement (its text includes its result), each ticked skill and education entry. A position's period
  goes with it and with its achievements. A fact the user did not tick, or hid, is not sent, and what the model writes for an id it
  was not sent is dropped. No name or contact details are sent. It also gets the company and role, the directions, the posting (cut
  to 6000 characters), the job terms the facts cover and those they lack, the pinned slot ids and, for a resume, the caps below.
- Caps come from `resume_pages`, the length of this resume (it is a setting of each resume, not of the app): 1 page (the default)
  is 3 bullets per position and 10 skills, 2 pages is 5 and 15, 3 pages is 7 and 20. Bullets over the cap and skills over the cap are dropped, and skills the
  model names that were not sent are dropped.
- The prompt is the versioned text file `adapters/inference/prompts/document_writer_v1.txt`.
- Every text must cite sent facts and may not say more than they do. A cited id that was not sent is dropped from the text, and a
  text left with none is rejected. A number, a capitalised name, a skill, a company or role, or a job term the facts lack is
  rejected. All rejected texts go back to the model in **one** repair call, with the reasons; nothing more is asked after it.
  A text still rejected is flagged: a bullet then shows the fact's own title (`not_rewritten`), a summary or paragraph is
  empty (`rejected`). `reasons` says why.
- `503` with `{"detail", "code": "llm_unavailable"}`: no model is set up, or it did not answer. `502` with
  `{"detail", "code": "ungrounded", "rejected": [{"slot", "reasons"}]}`: more than 30% of the written texts (not counting pinned
  ones) were still rejected after the repair, or none was kept. The client keeps its last draft.
- To keep a draft, send it as `generated` when saving.
