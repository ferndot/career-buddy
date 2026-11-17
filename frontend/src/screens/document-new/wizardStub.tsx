// Test helpers: a fake backend reached through fetch, and a way to drive the wizard to a step through its own buttons.
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { renderShell } from '../../test/render'
import { NewDocumentScreen } from './NewDocumentScreen'

const line = (text: string, id: string | null = null, field = '') => ({ text, source_fact_id: id, origin: 'fact', field, cites: [] })
const SECTIONS = ['Summary', 'Experience', 'Education', 'Skills']
const STYLES = [
  { id: 'direct', label: 'Direct and concise', instructions: 'Write it direct.' },
  { id: 'narrative', label: 'Narrative story', instructions: 'Tell a story.' },
]
const base = { formats: ['docx', 'pdf'], required: [], optional: [] }
export const templates = [
  { ...base, id: 'resume-classic', kind: 'resume', label: 'Classic resume', sections: SECTIONS, layout: { header: 'centered', side: [], css: '' }, instructions: 'Classic style.', styles: [] },
  { ...base, id: 'resume-sidebar', kind: 'resume', label: 'Sidebar resume', sections: SECTIONS, layout: { header: 'plain', side: ['Education', 'Skills'], css: '' }, instructions: 'Sidebar style.', styles: [] },
  { ...base, id: 'cover-letter', kind: 'letter', label: 'Cover letter', sections: [], layout: { header: 'plain', side: [], css: '' }, instructions: 'Letter style.', styles: STYLES },
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

// A cover letter as the preview endpoint returns it before anyone wrote it: the name and no sections.
const letter = (missing: string[]) => ({
  ...preview(missing),
  document: {
    name: line('Ada', 'person', 'title'), intro: [], label: 'Cover Letter',
    sections: [], // as the backend sends an unwritten letter: its empty body section is dropped
  },
})

const text = (slot: string, t: string, fact_ids: string[] = []) => ({ slot, text: t, fact_ids })
const item = (x: { slot?: string; text?: string; fact_ids?: string[]; position_id?: string; heading?: string; bullets?: ReturnType<typeof text>[] }) =>
  ({ slot: '', text: '', fact_ids: [], position_id: '', heading: '', bullets: [], ...x })

/** What the writer returns, by kind of document: the document as sections of items, each text with its slot id. A letter is one `body` block of paragraphs. */
export const DRAFTS = {
  resume: {
    sections: [
      { key: 'summary', title: 'Summary', items: [item(text('summary', 'Generated summary', ['person']))] },
      { key: 'experience', title: 'Experience', items: [item({ position_id: 'p1', heading: 'Engineer, Acme', bullets: [text('bullet:b1', 'Generated bullet', ['b1'])] })] },
    ],
    slots: { summary: 'Generated summary', 'bullet:b1': 'Generated bullet' },
    flags: {},
  },
  letter: {
    sections: [{ key: 'body', title: '', items: [item(text('para:1', 'Generated one', ['p1'])), item(text('para:2', 'Generated two', ['b1'])), item(text('para:3', 'Generated three', ['p1']))] }],
    slots: { 'para:1': 'Generated one', 'para:2': 'Generated two', 'para:3': 'Generated three' },
    flags: {},
  },
}

export type Calls = { method: string; url: string; body?: Record<string, unknown> }[]

/** Answers every wizard request. `calls` records them in order. `model` is whether an LLM connection is active; `generate` replaces the writer's answer. */
export function stubApi(missing: string[] = [], model = true, generate?: (asked: Record<string, unknown>) => Response, job = { title: '', company: '' }) {
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
      : u.includes('preview') ? preview(missing)
      : u.endsWith('/api/facts') ? [{ id: 'person', kind: 'Person', title: 'Ada', attributes: {}, source: '' }]
      : u.includes('/api/fit') ? { ...job, must_have: [], nice_to_have: [], missing_must_have: [], missing_nice_to_have: [] }
      : []
    return new Response(JSON.stringify(body))
  }))
  return calls
}

const next = () => fireEvent.click(screen.getByRole('button', { name: /^Next/ }))

/** Opens the wizard and clicks through to `step` with these documents chosen. */
export async function openAt(step: 2 | 3 | 4 | 5, kinds: ('Resume' | 'Cover letter')[] = ['Resume']) {
  renderShell(<NewDocumentScreen />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Python engineer with Kubernetes' } })
  next() // the model reads the posting first; step 2 follows, or the reading page waits for a retry without a model
  await waitFor(() => expect(screen.queryByRole('checkbox', { name: 'Resume' }) ?? screen.queryByRole('button', { name: 'Continue without requirements' })).toBeTruthy())
  if (screen.queryByRole('button', { name: 'Continue without requirements' })) fireEvent.click(screen.getByRole('button', { name: 'Continue without requirements' }))
  await screen.findByRole('checkbox', { name: 'Resume' })
  if (step === 2) return
  for (const k of kinds) fireEvent.click(screen.getByRole('checkbox', { name: k }))
  next()
  if (step === 3) return
  next()
  if (step === 4) return
  if (kinds.includes('Cover letter')) {
    fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
    fireEvent.click(screen.getByRole('tab', { name: /Resume/ }))
  }
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled())
  next()
  await screen.findByRole('button', { name: 'Word' }) // the last step shows once the text is written
}
