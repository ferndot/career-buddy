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
| `POST /api/documents/generate` | The document the model writes from every visible fact: sections of items, in the template's order. See below |
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

`POST /api/documents/generate` takes the same body as the other endpoints plus `resume_pages` (`"default"` or `1`, default `"default"`:
how long this resume should be; a letter ignores it; `422` for any other value), `instructions` (free text, at most 2000
characters, `422` over that, empty allowed: the user's direction for tone, length and emphasis), `pinned` (slot ids the user
wrote themselves; their text replaces the writer's) and `template_instructions` (free text, at most 4000 characters, empty by
default: how the chosen template and letter style want the text written. The wizard sends the template's `instructions`
followed by the chosen style's `instructions`. Empty adds nothing). `POST /api/saved-documents` takes the same field and keeps
it, so regenerating a saved document writes in the same style. A `cover-letter` is written from `job_text`; the wizard also sends the posting review's title and company as `inputs.role` and `inputs.company`. A letter with no `job_text` and no company and role is `422`. An unknown
template is `404`. Nothing is stored. A model is required: there is no text made without one.

The model does not fill fixed slots. It is given the context and writes **the best document it can**: one call, one JSON answer,
`{"sections": [{"key", "items": [...]}]}`, validated by the schema in `domain/written.py`. A real example of what it is sent is in
[example-writer-input-modern.md](example-writer-input-modern.md).

```json
{ "sections": [
    { "key": "summary", "title": "Summary", "items": [{ "slot": "summary", "text": "...", "fact_ids": ["<fact id>"] }] },
    { "key": "experience", "title": "Experience", "items": [
        { "position_id": "<position id>", "heading": "Senior Engineer, Acme (2019 - 2023)",
          "also": ["<older position id>"], "also_headings": ["Engineer, Acme (2016 - 2019)"],
          "bullets": [{ "slot": "bullet:<achievement id>", "text": "...", "fact_ids": ["<achievement id>", "..."] }] } ] },
    { "key": "skills", "title": "Skills", "items": [{ "slot": "skills", "text": "Languages: Python, Go", "fact_ids": ["<skill id>"] }] } ],
  "slots": { "summary": "...", "bullet:<id>": "..." },
  "flags": { "bullet:x": { "code": "not_rewritten", "reasons": ["..."] }, "summary": { "code": "rejected", "reasons": ["..."] } } }
```

**What the model is sent (the context).** The system message: the rules, the document kind's section shapes, the **general rules**
for the kind (below), the template's section list, the template's and the chosen letter style's instructions, and the resume length (`resume_pages`: how many bullets a position
and skills a resume may hold: `1` is exactly one page, 3 bullets per position and 10 skills; `"default"` lets the writer follow the general length rule, one page under about 10 years of experience and two for more, with at most 5 bullets and 15 skills). The user
message (JSON): every fact the document prints as `{id, kind, text, position_id, started, finished}` (summary, positions with
their dates, achievements with their result, skills, education; a hidden fact is not sent), the `sections` to write, the
company and role, the `directions`, the posting (cut to 6000 characters), the job terms the facts cover (`job_terms`) and lack
(`missing_terms`) and the `pinned` slot ids. No name or contact details are sent. The prompt is the versioned text file
`adapters/inference/prompts/document_writer_v8.txt`.

**What it writes.** The template's sections in the template's order (a resume's `sections`: for example summary, experience,
skills, education), each a list of items:

- `summary`: one item. `skills`: lines, each naming the skills it cites. `education`: one line per entry, each citing its education fact.
- `experience`: one item per position, `{position_id, also, bullets}`. The model chooses how many bullets a position gets (up to the cap)
  and how each reads, and may join achievements. A bullet cites the facts it rests on in `fact_ids`, an achievement of its own
  position first. A position's heading is the facts' own words, never the model's.
- **Several positions at one company.** The model decides the layout from the facts. *Same role family* (Analyst, Senior Analyst,
  Manager): it **condenses** them into one item, `position_id` the newest and `also` the older ones, with one combined set of
  bullets, the newest role's achievements first. *A big change of function* (Assistant Editor, then Web Developer): **separate**
  items, each with its own bullets and an empty `also`. *A very long tenure* (10+ years, several titles): **hybrid**, one item with
  full bullets for the current role and one or two for each earlier title. Every position keeps its own title and dates in every
  layout. `validated` sorts a group newest first, keeps a position in one item only, accepts a bullet that rests on an achievement
  of any position of its item, and allows the cap plus one bullet for each further position of the group. A condensed item prints
  one heading line per position (`<title>, <company> (<dates>)`, from the facts) and then its bullets, in the preview and in every
  download; the company name is repeated on each line, not printed once on its own. Slot ids are unchanged: `heading:<position id>`
  for each heading, `bullet:<first cited achievement id>` for a bullet, so saved documents and overrides keep working, and an item
  without `also` is what saved documents always held. The draft sends `also` (ids) and `also_headings` (their heading lines).
- A **cover letter is one block**: a single section `body` whose items are its paragraphs, in order. A paragraph is `para:<n>`,
  its index in the body (counting from 1). There is no per-paragraph section, greeting or sign-off.

`domain/written.validated` makes the answer fit to print before anything is checked: only the template's sections, each once,
in the template's order; cited ids the context lacks are dropped; empty items go; bullets over the cap, skills over the cap and
paragraphs over six go; a bullet that rests on no achievement of its position (or of a position its item condenses) is dropped; positions are in the career's order.

**Writing rules routes.** `GET /api/writing/rules` returns `{resume, letter}`, each `{rules, default, custom}`: `rules` is what the writer uses now, `default` the built-in list, `custom` whether the person saved their own. `PUT /api/writing/rules/{kind}` (`resume` or `letter`) with `{rules: [string]}` saves them and returns that kind's entry; each rule is trimmed, 1 to 300 characters, at most 20 rules, otherwise `422`; an empty list means the default. `DELETE /api/writing/rules/{kind}` returns the kind to the default (`204`). An unknown kind is `422`. They are stored in `writing-rules.json` in the data folder.

**Strictness routes.** `GET /api/writing/strictness` returns `{strictness, default}`: `strictness` is `strict`, `balanced` or `loose`, `default` is `balanced`. `PUT /api/writing/strictness` with `{strictness}` saves it and returns the same shape; any other value is `422`. It is stored beside the rules in `writing-rules.json` and read at each generate request into `Brief.strictness`. `domain/strictness.py` holds the levels. Checking splits in two: `domain/rewording.specifics` and `verify_prose` reject, at every level, a number, a name or tool-shaped word, a job term the profile lacks or a lost title, employer or degree that the cited facts do not give; the wording check (`rewording.wording`, and the length cap in `verify_prose`) is the only part the level changes: a bullet or education line may run 1.3 (strict), 1.8 (balanced) or 2.5 (loose) times the cited text, and prose 6, 8 or 10 times plus 300, 400 or 500 characters. Lowercase generic wording is not checked at any level.

**Fit.** After grounding, `domain/fit.fit` scores a draft against the posting terms the facts cover (`Brief.terms`, the first 10): the share used in the text (half of them is full marks), whether the summary names one, whether one of the first three bullets does, minus 0.2 for each coverage issue. Under 0.7 it adds a `weak_fit` issue, which names the reasons and the slots that may be rewritten, so the one revision aims at the posting. It is plain code, not a model judge.

**General rules.** `domain/writing_rules.py` holds the defaults as plain data: a tuple of rule strings per document kind
(`DEFAULT_RULES["resume"]`, `DEFAULT_RULES["letter"]`). The generate use case puts the kind's tuple in `Brief.rules` and the writer adds
it to the system message as "General rules for a resume/letter"; a different tuple replaces the default and an empty one adds
none. A person's own rules (Settings > Writing) are saved per kind and read at each generate request; none saved means the default. See [Override the writing rules](../how-to/override-the-writing-rules.md). The resume rules: plain headings and one date format; 3 to 6 bullets a role (5 to 8 for the current or most relevant role, 1 to 3
for older ones), each one or two lines; a strong, varied action verb first and results quantified where the facts give numbers; the most
space for the last 10 to 15 years, older roles condensed into an "Earlier" line or left out; one page under about 10 years, two for 10 or
more; no claim beyond the facts. The letter rules: 250 to 400 words in three or four short paragraphs, not repeating the resume, the exact
company and role from the posting, no cliches, no "To Whom It May Concern", no greeting or sign-off unless the template asks. They shape
style and selection only: the grounding rules are the prompt's, are unchanged, and the template's instructions and length win where they
differ. They are not repeated in the revision.

**Slot ids and the user's edits.** Every text has a slot id, the key of the user's own words (`overrides`) and of the saved layout:
`summary`, `skills`, `edu:<first cited education id>`, `para:<n>` and, for a bullet, `bullet:<first cited achievement id>`
(a repeat is `#2`, `#3`). A person's edit therefore survives a regenerate while the bullet still rests on the same fact, and an
edited paragraph while it is still the nth. A pinned slot is never lost: if the model wrote it, its text is blanked (the person's
words take its place); if the model left it out, it is added to its section, a bullet to its position.

**Checking.** Every text must cite sent facts and may not say more than they do. A cited id that was not sent is dropped, and a
text left with none is rejected. A number, a capitalised name, a skill, a company or role, or a job term the facts lack is
rejected; a bullet and an education line are held to the achievements or education entries they cite, with protected titles,
employers, degrees and schools unchanged; a skills line may name only skills it cites. All rejected texts go back to the model in
**one** revision (the model calls the same tool once more, told the reasons); only the rejected texts change and accepted text is kept as it is; nothing more is asked after it. A text still rejected is flagged: a bullet or education
line then shows the fact's own words (`not_rewritten`), any other text is empty (`rejected`). `reasons` says why.

- `503` with `{"detail", "code": "llm_unavailable"}`: no model is set up, it did not answer, or its answer is not a document of the shape above.
  `502` with `{"detail", "code": "ungrounded", "rejected": [{"slot", "reasons"}]}`: more than 30% of the written texts (not counting pinned
  ones or skills lines) were still rejected after the revision, or none was kept. The client keeps its last draft.
- To keep a draft, send its `sections` when saving (see [Saved documents API](saved-documents-api.md)).

## Reviewing a job posting

`POST /api/fit` with `{job_text}` asks the connected model what the posting requires. Only the posting is sent (cut to 6000
characters), never a fact. It answers `{title, company, must_have, nice_to_have, missing_must_have, missing_nice_to_have}`.

- Each term is a skill, tool, qualification or credential as the posting names it, at most 12 must-have and 8 nice-to-have.
  A term the posting does not contain, the company or title, a one-word generic term (`domain/review.py`) or a duplicate is dropped.
- `missing_*` are the terms whose meaningful words no career fact uses. The wizard asks about those only.
- With no model, or one that does not answer, the answer is 503 with `code: "llm_unavailable"`. There is no keyword fallback.
- The prompt is `adapters/inference/prompts/job_review_v1.txt`.
