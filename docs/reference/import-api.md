# Import API

## Import text

`POST /api/import/text` takes pasted plain text or Markdown. Headings such as Experience, Skills and Education help the offline reader. Position lines look like `Title at Organization, 2019 - 2023`, or three lines in a row: organization, title, dates. Bullets can be `-`, `*`, a round or square bullet character, or similar list marks.

## Import a file

`POST /api/import/file` takes a PDF, DOCX, TXT or MD file, up to 10 MB. It reads the text, then extracts facts the same way as pasted text.

| Status | Meaning |
|---|---|
| 413 | Over 10 MB |
| 415 | Unknown file type |
| 422 | Corrupt file, or a PDF with no text layer (scans need OCR, which is not supported) |

Two-column PDFs are read column by column. DOCX tables, text boxes and the header (contact details) are included.

The original bytes are kept as `sources/<sha256>.<ext>` and the key is recorded in the import event. See [Store originals in S3](../how-to/store-originals-in-s3.md).

For status and progress of a running import, see the [Sources API](sources-api.md).

## Fetch a job posting

`POST /api/job/fetch` takes `{"url": "..."}` and returns `{"text": "..."}`. The wizard uses it in its Job posting step.

The server refuses:

- Addresses on private, loopback or link-local networks. This covers the link and every redirect (at most 3).
- Links with a user name in them.
- Pages over 1 MB, and anything that is not HTML or plain text.
- Requests that take more than 10 seconds.

| Status | Meaning |
|---|---|
| 400 | Bad or private link |
| 413 | Too large |
| 415 | Wrong type |
| 422 | No readable text |
| 502 | The site returned an error |
| 504 | Timeout |

Pages that build their content with JavaScript give no text. Paste those by hand.

## Resume as Markdown or HTML

`GET /api/resume/markdown` and `GET /api/resume/html` return the Classic resume. Other formats and templates go through the [Documents API](documents-api.md).
