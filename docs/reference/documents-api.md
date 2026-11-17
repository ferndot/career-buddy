# Documents API

All document endpoints take `{template, format?, job_text?, inputs?, overrides?}`.

- There is no selection. The body has no `selection`, `skill_ids` or `education_ids` field, and no response reports one. Every
  visible fact goes to the writer and into the document: all bullets, skills and education entries. A fact the user hid is
  left out. Bullets and skills are ordered by how well they match `job_text`. A field the body does not name is ignored.

The document wizard has five steps: Job posting, Documents, Missing requirements, Template, Preview and download. Between Template and Preview and download the model writes the text, on its own page that shows any failure and offers a retry. They call
`POST /api/job/fetch` (see [Import API](import-api.md)), `POST /api/fit`, `POST /api/documents/generate`,
`POST /api/documents/preview` and `POST /api/documents/render`.

To keep a rendered file, see [Saved documents API](saved-documents-api.md).

| Endpoint | Purpose |
|---|---|
| `GET /api/templates` | `[{id, kind, label, formats, required, optional, sections, layout, instructions, styles}]` for the five templates. See below |
| `POST /api/documents/render` | The file, with `Content-Disposition`. `format` is `docx`, `pdf`, `txt`, `markdown` or `html` |
| `POST /api/documents/preview` | `{lines, document, tailoring, markers, ats}`. `ats` checks `format` (default `docx`) |
| `POST /api/documents/check` | `{passes, issues}` for one format |
| `POST /api/documents/generate` | A draft of the text a document needs, written from every visible fact. See below |
| `POST /api/documents/suggest` | Needs `job_text`. `{suggestions: [{fact_id, before, after}], rejected: [{fact_id, reasons}]}`: model wordings for the bullets, each checked against the facts. `503` with no model |

Templates: `resume-classic` (single column), `resume-sidebar` (a side column for education and skills), `resume-modern` (a header
band), `cover-letter` and `cover-letter-modern` (the job-board letters: no required inputs, `recipient` optional). A missing or
blank required input returns 422 and names it. Unknown inputs are ignored. An unknown template, such as the removed
`cover-letter-email`, is `404`.

A template is data (`domain/templates.py`). Besides `id`, `kind`, `label` and the inputs it lists:

- `sections`: a resume's headings in order (empty for a letter).
- `layout`: `{header: "plain" | "centered" | "band", side: [headings], css}`. `side` are the headings of the trailing sections
  that sit in a side column. The saved html wraps its parts in `header`, `.cols`, `.main` and `.side` and the saved css holds the
  template's `css`; the wizard draws the same arrangement. Downloads in docx, pdf and txt stay single column, which is what ATS
  readers parse best.
- `instructions`: what the writer is told about the template's style.
- `styles`: a letter's suggested styles, `[{id, label, instructions}]` (`direct`, `narrative`, `formal`); empty for a resume.

## ATS check is a warning

Every render and preview reads the file back and runs `domain/ats.check`. A failing check never blocks the download.
`render` adds `X-ATS-Issues: code,code` (absent when the check passes). The codes are `coverage`, `order`, `name`,
`headings`, `table`, `text_box`, `header_footer`, `images`, `text_layer` and `glyphs`.

## Generating the text

`POST /api/documents/generate` takes the same body as the other endpoints plus `resume_pages` (`1`, `2` or `3`, default `1`:
how long this resume should be; a letter ignores it; `422` for any other value), `instructions` (free text, at most 2000
characters, `422` over that, empty allowed: the user's direction for tone, length and emphasis), `pinned` (slot ids the user
wrote themselves; the writer leaves them alone) and `template_instructions` (free text, at most 4000 characters, empty by
default: how the chosen template and letter style want the text written. The wizard sends the template's `instructions`
followed by the chosen style's `instructions`. Empty adds nothing). `POST /api/saved-documents` takes the same field and keeps
it, so regenerating a saved document writes in the same style. A `cover-letter` is written from `job_text`; the wizard also sends the posting review's title and company as `inputs.role` and `inputs.company`. A letter with no `job_text` and no company and role is `422`. An unknown
template is `404`. Nothing is stored. A model is required: there is no text made without one.

```json
{ "slots": { "summary": "...", "bullet:<id>": "...", "skills": "Python, Go", "para:1": "..." },
  "cites": { "summary": ["<fact id>"] },
  "flags": { "bullet:x": { "code": "not_rewritten", "reasons": ["..."] }, "summary": { "code": "rejected", "reasons": ["..."] } } }
```

- A resume gets `summary`, `bullet:<achievement id>` and `skills`; a letter gets `para:<n>` (a letter is its header and these paragraphs: no code writes its words).
  The ids are the slot ids of [saved documents](saved-documents-api.md). A slot that is absent keeps what the facts say.
- The model is sent every fact the document prints, as `{id, kind, text, position_id, started, finished}`: the summary, each
  position, each achievement (its text includes its result), each skill and each education entry that the user can see. A
  position's `started` and `finished` dates go with it and with its achievements. A fact the user hid is not sent, and what the model writes for an id
  it was not sent is dropped. No name or contact details are sent. It also gets the company and role, the directions, the posting (cut
  to 6000 characters), the job terms the facts cover and those they lack, the pinned slot ids and, for a resume, the caps below.
- Caps come from `resume_pages`, the length of this resume (it is a setting of each resume, not of the app): 1 page (the default)
  is 3 bullets per position and 10 skills, 2 pages is 5 and 15, 3 pages is 7 and 20. Bullets over the cap and skills over the cap are dropped, and skills the
  model names that were not sent are dropped.
- The prompt is the versioned text file `adapters/inference/prompts/document_writer_v4.txt`.
- Every text must cite sent facts and may not say more than they do. A cited id that was not sent is dropped from the text, and a
  text left with none is rejected. A number, a capitalised name, a skill, a company or role, or a job term the facts lack is
  rejected. All rejected texts go back to the model in **one** repair call, with the reasons; nothing more is asked after it.
  A text still rejected is flagged: a bullet then shows the fact's own title (`not_rewritten`), a summary or paragraph is
  empty (`rejected`). `reasons` says why.
- `503` with `{"detail", "code": "llm_unavailable"}`: no model is set up, or it did not answer. `502` with
  `{"detail", "code": "ungrounded", "rejected": [{"slot", "reasons"}]}`: more than 30% of the written texts (not counting pinned
  ones) were still rejected after the repair, or none was kept. The client keeps its last draft.
- To keep a draft, send it as `generated` when saving.

## Reviewing a job posting

`POST /api/fit` with `{job_text}` asks the connected model what the posting requires. Only the posting is sent (cut to 6000
characters), never a fact. It answers `{title, company, must_have, nice_to_have, missing_must_have, missing_nice_to_have}`.

- Each term is a skill, tool, qualification or credential as the posting names it, at most 12 must-have and 8 nice-to-have.
  A term the posting does not contain, the company or title, a one-word generic term (`domain/review.py`) or a duplicate is dropped.
- `missing_*` are the terms whose meaningful words no career fact uses. The wizard asks about those only.
- With no model, or one that does not answer, the answer is 503 with `code: "llm_unavailable"`. There is no keyword fallback.
- The prompt is `adapters/inference/prompts/job_review_v1.txt`.
