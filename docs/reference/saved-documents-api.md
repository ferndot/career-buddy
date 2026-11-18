# Saved documents API

A saved document is a small folder in the object store (an S3 server with `CAREER_BUDDY_STORAGE=s3`, such as SeaweedFS,
otherwise `<data dir>/objects`): `documents/<id>/`. The `id` is 32 lowercase hex characters; any other id answers `404`.

A saved document is **live**. It is kept as a layout plus what the user and the writer added, not as text:

| Key | Content |
|---|---|
| `meta.json` | the record, written last |
| `document.html` | the layout, with tags `h1 h2 h3 p ul li` only. It holds no text from the facts and none the model wrote. When the document was saved with the model's `sections`, its structure is theirs: the bullets, paragraphs and lines the model chose, each a slot |
| `document.css` | the look, from the saved `font` and `paper` |
| `overrides.json` | `{slot id: the user's own wording}`; `{}` when nothing was written by hand |
| `generated.json` | `{slot id: {text, source}}`: what the writer wrote. `source` is what the slot's facts said then, for a bullet, an education line and the skills lines |
| `source.json` | what the document was built from: `template`, `job_text`, `inputs`, the `instructions` given to the writer and `resume_pages` (`"default"` or `1`: this resume's length; a document saved with `2` or `3` reads as `"default"`) and `job_url` (where the posting was found: an http(s) link, else `""`, also for a document saved before it was kept). No text |

Every text line in `document.html` is a **slot**: `data-slot` (the slot id), `data-fact-id` (the fact or facts it shows, separated
by spaces), `data-field` (which value of the fact) and `data-origin` (`fact`, `user`, `suggestion`, `boilerplate`). Section titles
are fixed headings and have no slot.

### Slot ids

| Slot id | Shows |
|---|---|
| `name`, `location`, `headline`, `summary` | the person's name, location, headline and summary |
| `heading:<position id>` | a position's `Title, Employer (dates)` line |
| `bullet:<achievement id>` | an achievement, or a bullet the model wrote: the id is the first achievement it cites (a repeat gets `#2`) |
| `edu:<education id>` | an education entry |
| `skills` | the skills, joined with commas, or the model's skills lines (`skills`, `skills#2`). Their ids are in `data-fact-id`, fixed when the document is saved |
| `para:<n>` | a letter's paragraphs: its body is one block, and a paragraph is its index in it, counted from 1 |

An id that would repeat gets `#2`, `#3`. The ids are stable, so `GET .../content` and `POST /api/documents/generate` use the same ones.

### Where the text of a slot comes from

It is found when the document is read, every time, in this order:

1. the slot's entry in `overrides.json` (the user's own words);
2. the slot's entry in `generated.json`, unless it is stale: a bullet, an education line or a skills line whose facts say something else now
   (the fact was edited or deleted) shows the facts instead. A summary or a paragraph rests on many facts and never goes stale;
3. the current value of the fact it is bound to, so a later edit to the career facts shows in the next download. A fact
   that was deleted or merged away leaves its slot empty, and an empty line is left out;
4. the placeholder: the layout's own text, empty for a letter's slots (no code writes a letter's words). Placeholder text never resolves from a fact.

So editing a fact after saving changes the download, except where the user's own words (an override) or the writer's text for a
summary or paragraph stand in its place.

A freeform edit of the whole document is saved in `overrides` too. A text with newlines is several lines of the slot's kind (a
bullet followed by two more bullets; paragraphs for a summary or a letter), which is how a line is added after a slot. A blank
text removes the line, and a line moved is a removal and an addition. The line is read back this way at every download, and
regenerating pins a blank slot like any other override, so a removed line stays removed.

`POST` takes the user's wording in `overrides` (a key is a slot id, or a bare fact id for that fact's bullet; a key that names no
slot is dropped; see below for several lines and a blank text) and the writer's document in `sections` (the `sections` of `POST /api/documents/generate`: `[{key, items}]`; the
`slot`, `title` and `heading` fields it carries are ignored and worked out again). `sections` are the layout: the structure the
model chose, its text going to `generated.json`. Keys the template does not have, bullets with no cited fact and positions the
career lacks are left out. With no `sections` the layout is the template filled from the facts (a document saved before the
model wrote the whole document is read and downloaded as it always was, and can be regenerated: the new text replaces its layout
and `generated.json`, and its `overrides.json` keys still name slots). A letter saved with only `para:<n>` overrides is a body of
those paragraphs, up to the highest `n`.

At download time the layout is read with every slot resolved, then converted.

| Endpoint | Purpose |
|---|---|
| `GET /api/saved-documents` | List of records, newest first |
| `POST /api/saved-documents` | Build and save as HTML. `201` with the record |
| `GET /api/saved-documents/{id}/content` | `{html, css, overrides, generated, source, slots}`. `generated` is `{slot id: text}`; `source` is `source.json` (`null` for a document saved before it was kept); `slots` is the text of every slot as it reads now. `404` unknown |
| `POST /api/saved-documents/{id}/regenerate` | Body `{"instructions": "", "resume_pages": null}` (empty or left out keeps the saved directions and the saved length; a value of `1`, `2` or `3` is used and kept). Writes the document again from the facts as they are now, and replaces the layout and `generated.json`. Every slot with an override is pinned: the writer's text for it is replaced by the user's words, and it is added if the writer left it out. Returns the draft (see [Documents API](documents-api.md)). `503` and `502` as for generate, with nothing changed; `409` for a document saved before `source.json`; `404` unknown |
| `GET /api/saved-documents/{id}/file?format=docx\|pdf\|txt` | The file, with `Content-Disposition: attachment`. Default `docx`. `404` unknown; `422` other format; `503` PDF without Chromium |
| `DELETE /api/saved-documents/{id}` | Remove every file. `204`; `404` unknown |

A record is `{id, label, template, filename, created_at, ats_issues}`. `created_at` is ISO 8601 in UTC.
`ats_issues` lists the codes of the ATS checks that failed for the docx at save time (see [Documents API](documents-api.md)).
`filename` has no extension (the download adds one). The download also sends `X-ATS-Issues` (the failed checks for that format)
when there are any.

`POST` takes the body of `POST /api/documents/render` without `format`
(`template`, `job_text`, `inputs`, `overrides`, `font`, `paper`; `overrides` as above)
plus `job_title` and `company` (default empty), `job_url` (default empty), `label` (default empty), `sections` (default `[]`),
`instructions` (default empty, at most 2000 characters, kept for regenerating) and `resume_pages` (`"default"` or `1`, default `"default"`: the
length of this resume, kept for regenerating; a letter ignores it). An unknown template answers `404`.
Missing required inputs answer `422`. A `format` field is ignored.

**Naming.** With no `label`, the record's `label` is `job_title`, then ` · company` when there is one (`Data Platform Engineer · Contoso Data`),
and `filename` is `job_title` with every run of other characters than letters and digits made a hyphen (`Data-Platform-Engineer`).
With no `job_title` the label is the template's label and `filename` is the profile name and the template (`Jane-Doe-Resume`). A `company` alone names nothing.
A `label` that is sent wins for the label. Documents saved before this keep their labels.

**The listing link.** `job_url` is kept in `source.json` only when it is a single `http://` or `https://` address; anything else is stored as empty.
`GET /api/saved-documents/{id}/content` returns it as `source.job_url`, with the document's `html`, `css` and `slots`, which is all the app's
detail page (`/documents/{id}`) needs: the title (the record's `label`), the link (or "No link saved") and the document as it reads now.

docx and txt are made from the stored HTML and ignore its CSS. PDF is made the same way for now, so it also ignores the CSS.
