// Document helpers shared by the Documents list and the new-document wizard.
import { apiFetch, apiUrl, endpoints } from '../../api'

export type Template = {
  id: string
  kind: 'resume' | 'letter'
  label: string
  formats: string[]
  required: string[]
  optional: string[]
}
/** The model's review of a job posting. `missing_*` are the terms none of the career facts cover. */
export type Fit = {
  title: string
  company: string
  must_have: string[]
  nice_to_have: string[]
  missing_must_have: string[]
  missing_nice_to_have: string[]
}
export type Issue = { code: string; message: string }
export type DocLine = { text: string; source_fact_id: string | null; origin: string; field: string; cites: string[] } // field and cites place the line in a saved layout (see slotDoc)
export type DocEntry = { heading: DocLine | null; paragraph: DocLine | null; bullets: DocLine[] }
export type PreviewDoc = { name: DocLine; intro: DocLine[]; sections: { title: string; entries: DocEntry[] }[]; label: string }
export type Preview = {
  lines: string[]
  document: PreviewDoc
  tailoring: { matched: string[]; missing: string[] }
  ats: { format: string; passes: boolean; issues: Issue[] }
}
/** The body shared by preview and render (the backend's TailorRequest). */
export type TailorBody = {
  template: string
  job_text: string
  inputs: Record<string, string>
  overrides?: Record<string, string> // the user's own wording, by slot id ("summary", "bullet:<fact id>", "para:<n>", "headline", ...)
}

/** The preview query shared by the template step (on screen) and the save (letters read their paragraphs from it). */
export const previewQuery = (body: TailorBody) => ({ queryKey: ['details-preview', body], queryFn: () => getPreview(body) })

export const getTemplates = () => apiFetch<Template[]>(endpoints.templates.list())
export const getFit = (job_text: string) =>
  apiFetch<Fit>(endpoints.documents.fit(), { method: 'POST', body: { job_text } })
export const getPreview = (body: TailorBody, format = 'docx') =>
  apiFetch<Preview>(endpoints.documents.preview(), { method: 'POST', body: { ...body, format } })
export const fetchJobText = (url: string) =>
  apiFetch<{ text: string }>(endpoints.job.fetch(), { method: 'POST', body: { url } })

/** A slot the person should look at: a bullet the writer could not reword (it shows the fact's own words), or text left empty. */
export type Flag = { code: 'not_rewritten' | 'rejected'; reasons: string[] }
/** The writer's draft: slot id -> text. Nothing is stored; saving the document keeps it as generated text. */
export type Generated = {
  slots: Record<string, string>
  cites: Record<string, string[]>
  flags: Record<string, Flag>
}
export const MAX_INSTRUCTIONS = 2000
export type ResumePages = 1 | 2 | 3
/** `pinned` are the slots the user wrote themselves: the writer leaves them alone. `resume_pages` is how long a resume should be. */
export const generateText = (body: TailorBody & { instructions: string; pinned: string[]; resume_pages: ResumePages }) =>
  apiFetch<Generated>(endpoints.documents.generate(), { method: 'POST', body })

export type SavedDocument = {
  id: string
  label: string
  template: string
  filename: string
  created_at: string
  ats_issues: string[]
}
export type SaveBody = TailorBody & {
  overrides: Record<string, string> // the user's own wording by slot id
  generated: Record<string, string> // the writer's text by slot id, kept apart so regenerating never touches an override
  instructions: string // the directions given to the writer, kept for regenerating
  resume_pages: ResumePages // this resume's length, kept for regenerating
  font: 'sans' | 'serif'
  paper: 'letter' | 'a4'
  label: string
}

export const SAVED_KEY = ['saved-documents']
export const getSavedDocuments = () => apiFetch<SavedDocument[]>(endpoints.savedDocuments.list())
export const saveDocument = (body: SaveBody) =>
  apiFetch<SavedDocument>(endpoints.savedDocuments.create(), { method: 'POST', body })
export const deleteSavedDocument = (id: string) =>
  apiFetch<void>(endpoints.savedDocuments.remove(id), { method: 'DELETE' })

/** Saves a fetched file through the browser, or throws the server's error detail. */
async function saveResponse(res: Response, fallbackName: string): Promise<void> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = String(((await res.json()) as { detail?: unknown }).detail ?? detail)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail || `Download failed (${res.status})`)
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1]
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name ?? fallbackName
  a.click()
  URL.revokeObjectURL(url)
}

/** Renders on the server and saves the file through the browser. */
export async function downloadDocument(body: TailorBody, format: string): Promise<void> {
  const res = await fetch(apiUrl(endpoints.documents.render()), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, format }),
  })
  return saveResponse(res, `document.${format}`)
}

export const DOWNLOAD_FORMATS = [
  { format: 'docx', label: 'Word' },
  { format: 'pdf', label: 'PDF' },
  { format: 'txt', label: 'Text' },
] as const

export async function downloadSaved(doc: SavedDocument, format: string): Promise<void> {
  return saveResponse(await fetch(apiUrl(endpoints.savedDocuments.file(doc.id, format))), `${doc.filename}.${format}`)
}
