// Test helpers: a fake backend reached through fetch, and a way to drive the wizard to a step through its own buttons.
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { renderApp } from '../../test/render'
import { NewDocumentScreen } from './NewDocumentScreen'

const line = (text: string, id: string | null = null, field = '') => ({ text, source_fact_id: id, origin: 'fact', field, cites: [] })
const profile = {
  name: 'Ada', attributes: { headline: 'Engineer' }, skills: ['Python', 'SQL'], skill_ids: ['s1', 's2'],
  positions: [{ id: 'p1', title: 'Engineer', organization: 'Acme', attributes: {}, achievements: ['Shipped it'], achievement_ids: ['b1'] }],
  education: [{ id: 'e1', school: 'MIT', degree: 'BS' }],
}
const templates = [
  { id: 'resume-classic', kind: 'resume', label: 'Classic resume', formats: ['docx', 'pdf'], required: [], optional: [] },
  { id: 'cover-letter', kind: 'letter', label: 'Cover letter', formats: ['docx', 'pdf'], required: ['role', 'company'], optional: [] },
]
const preview = (missing: string[]) => ({
  lines: ['Ada'],
  document: {
    name: line('Ada', 'person', 'title'), intro: [], label: 'Resume',
    sections: [
      { title: 'Summary', entries: [{ heading: null, paragraph: line('Builds things', 'person', 'summary'), bullets: [] }] },
      { title: 'Experience', entries: [{ heading: line('Engineer, Acme', 'p1', 'heading'), paragraph: null, bullets: [line('Shipped it', 'b1', 'title')] }] },
    ],
  },
  tailoring: { matched: ['Python'], missing },
  ats: { format: 'docx', passes: true, issues: [] },
})

// A cover letter as a draft stub lays it out: two placeholder paragraphs (para:1, para:2) and the name. Stub text, not app output.
const letter = (missing: string[]) => ({
  ...preview(missing),
  document: {
    name: line('Ada', 'person', 'title'), intro: [], label: 'Cover Letter',
    sections: [{ title: '', entries: [
      ['Paragraph one', ''], ['Paragraph two', ''], ['Ada', 'title'],
    ].map(([text, field]) => ({ heading: null, paragraph: line(text, 'person', field), bullets: [] })) }],
  },
})

/** What the writer returns, by kind of document. */
export const DRAFTS = {
  resume: { slots: { summary: 'Generated summary', 'bullet:b1': 'Generated bullet' }, cites: {}, flags: {} },
  letter: { slots: { 'para:1': 'Generated one', 'para:2': 'Generated two', 'para:3': 'Generated three' }, cites: {}, flags: {} },
}

export type Calls = { method: string; url: string; body?: Record<string, unknown> }[]

/** Answers every wizard request. `calls` records them in order. `model` is whether an LLM connection is active; `generate` replaces the writer's answer. */
export function stubApi(missing: string[] = [], model = true, generate?: (asked: Record<string, unknown>) => Response) {
  const calls: Calls = []
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} }))
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    calls.push({ method, url: u, body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined })
    const asked = typeof init?.body === 'string' ? JSON.parse(init.body) : {}
    if (u.endsWith('/api/llm/connections')) return new Response(JSON.stringify({ active: model ? 'c1' : null, connections: [] }))
    if (u.endsWith('/api/documents/generate') && generate) return generate(asked)
    if (u.endsWith('/api/documents/generate')) return new Response(JSON.stringify(asked.template === 'cover-letter' ? DRAFTS.letter : DRAFTS.resume))
    if (u.endsWith('/api/documents/preview') && asked.template === 'cover-letter') return new Response(JSON.stringify(letter(missing)))
    if (method === 'POST' && u.endsWith('/api/saved-documents')) {
      return new Response(JSON.stringify({ id: 'd1', label: 'x', template: 'resume-classic', format: '', filename: 'resume', created_at: '2026-11-14T10:00:00Z', ats_issues: [], version: 2 }), { status: 201 })
    }
    if (method === 'POST' && u.endsWith('/api/facts')) return new Response(JSON.stringify({ id: 'new' }), { status: 201 })
    if (u.includes('/file')) return new Response('data', { headers: { 'Content-Disposition': 'attachment; filename="resume.txt"' } })
    const body = u.includes('templates') ? templates
      : u.includes('/api/profile') ? profile
      : u.includes('preview') ? preview(missing)
      : u.endsWith('/api/facts') ? [{ id: 'person', kind: 'Person', title: 'Ada', attributes: {}, source: '' }]
      : u.includes('/api/fit') ? { positions: ['Engineer'], matched_skills: [] }
      : []
    return new Response(JSON.stringify(body))
  }))
  return calls
}

const next = () => fireEvent.click(screen.getByRole('button', { name: /^Next/ }))

/** Opens the wizard and clicks through to `step` with these documents chosen. */
export async function openAt(step: 2 | 3 | 4 | 5, kinds: ('Resume' | 'Cover letter')[] = ['Resume']) {
  renderApp(<NewDocumentScreen />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Python engineer with Kubernetes' } })
  next()
  if (step === 2) return
  for (const k of kinds) fireEvent.click(screen.getByRole('checkbox', { name: k }))
  next()
  if (step === 3) return screen.findByLabelText('SQL')
  await screen.findByLabelText('SQL')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled())
  next()
  if (step === 4) return
  if (kinds.includes('Cover letter')) {
    fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
    fireEvent.change(await screen.findByLabelText(/role/i), { target: { value: 'Engineer' } })
    fireEvent.change(screen.getByLabelText(/company/i), { target: { value: 'Acme' } })
    fireEvent.click(screen.getByRole('tab', { name: /Resume/ }))
  }
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled())
  next()
}
