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
export type Position = {
  id: string
  title: string
  organization: string
  attributes: Record<string, string>
  achievements: string[]
  achievement_ids: string[]
}
export type Education = { id: string; school: string; degree: string }
export type Profile = {
  name: string
  attributes: Record<string, string>
  positions: Position[]
  education: Education[]
  skills: string[]
  skill_ids: string[] // parallel to skills
}
export type Fit = { positions: string[]; matched_skills: string[] }
export type Issue = { code: string; message: string }
export type Preview = {
  lines: string[]
  tailoring: { matched: string[]; missing: string[] }
  ats: { format: string; passes: boolean; issues: Issue[] }
}
/** The body shared by preview and render (the backend's TailorRequest). */
export type TailorBody = {
  template: string
  job_text: string
  selection?: string[]
  skill_ids?: string[]
  education_ids?: string[]
  inputs: Record<string, string>
}

export const getTemplates = () => apiFetch<Template[]>(endpoints.templates.list())
export const getProfile = () => apiFetch<Profile>(endpoints.profile.get())
export const getFit = (job_text: string) =>
  apiFetch<Fit>(endpoints.documents.fit(), { method: 'POST', body: { job_text } })
export const getPreview = (body: TailorBody, format = 'docx') =>
  apiFetch<Preview>(endpoints.documents.preview(), { method: 'POST', body: { ...body, format } })
export const fetchJobText = (url: string) =>
  apiFetch<{ text: string }>(endpoints.job.fetch(), { method: 'POST', body: { url } })

export type SavedDocument = {
  id: string
  label: string
  template: string
  format: string
  filename: string
  created_at: string
  ats_issues: string[]
}
export type SaveBody = Omit<TailorBody, 'selection' | 'skill_ids' | 'education_ids'> & {
  selection: string[] | null
  skill_ids: string[] | null
  education_ids: string[] | null
  overrides: Record<string, string>
  format: string
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

export async function downloadSaved(doc: SavedDocument): Promise<void> {
  return saveResponse(await fetch(apiUrl(endpoints.savedDocuments.file(doc.id))), doc.filename)
}
