import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { renderApp } from '../../test/render'
import { NewDocumentScreen } from './NewDocumentScreen'

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

const URL_ = 'https://jobs.example.com/123'
const jobInput = () => screen.getByLabelText('Job posting link')

test('starts on a single job link box, with Next disabled until a job is available', () => {
  renderApp(<NewDocumentScreen />)
  expect(screen.getByRole('heading', { name: 'Where is the job posting?' })).toBeInTheDocument()
  expect(jobInput()).toBeInTheDocument()
  expect(screen.queryByLabelText('Job posting text')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Fetch' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
})

test('always reopens on the first step, even after leaving from a later one', () => {
  const { unmount } = renderApp(<NewDocumentScreen />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Pasted posting' } })
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 2 of 4 · Type and template')
  unmount()
  renderApp(<NewDocumentScreen />)
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 1 of 4 · Job posting')
})

test('fetches the job once the link is entered and enables Next', async () => {
  const fetchMock = vi.fn(async (_u: string) => new Response(JSON.stringify({ text: 'Senior Engineer at Acme' })))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<NewDocumentScreen />)
  fireEvent.change(jobInput(), { target: { value: URL_ } })
  expect(fetchMock).not.toHaveBeenCalled() // waits for a pause in typing
  await screen.findByText('Got it: jobs.example.com')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(String(fetchMock.mock.calls[0][0])).toContain('/api/job/fetch')
  expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
})

test('ignores the response for an older link', async () => {
  const pending: Record<string, (r: Response) => void> = {}
  vi.stubGlobal('fetch', vi.fn((_u: string, init: RequestInit) => new Promise<Response>((res) => { pending[JSON.parse(String(init.body)).url] = res })))
  renderApp(<NewDocumentScreen />)
  fireEvent.change(jobInput(), { target: { value: URL_ } })
  await waitFor(() => expect(pending[URL_]).toBeDefined())
  fireEvent.change(jobInput(), { target: { value: URL_ + '4' } })
  await waitFor(() => expect(pending[URL_ + '4']).toBeDefined())
  pending[URL_ + '4'](new Response(JSON.stringify({ text: 'new job' })))
  await screen.findByText('Got it: jobs.example.com')
  pending[URL_](new Response(JSON.stringify({ text: 'old job' })))
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  await waitFor(() => expect(screen.getByLabelText('Job posting text')).toHaveValue('new job'))
})

test('shows an inline error and the paste fallback when the page cannot be read', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'nope' }), { status: 422 })))
  renderApp(<NewDocumentScreen />)
  fireEvent.change(jobInput(), { target: { value: URL_ } })
  await screen.findByText('Could not read this page. Paste the text instead.')
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Pasted posting' } })
  expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
})

test('pasted job text works without a link', () => {
  renderApp(<NewDocumentScreen />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Pasted posting' } })
  expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
})

test('saves the selection through the saved-documents API', async () => {
  const profile = {
    name: 'Ada', attributes: {}, skills: ['Python', 'SQL'], skill_ids: ['s1', 's2'],
    positions: [{ id: 'p1', title: 'Engineer', organization: 'Acme', attributes: {}, achievements: ['Shipped it'], achievement_ids: ['b1'] }],
    education: [{ id: 'e1', school: 'MIT', degree: 'BS' }],
  }
  const template = { id: 'resume-classic', kind: 'resume', label: 'Classic resume', formats: ['docx', 'pdf'], required: ['role', 'company'], optional: [] }
  const preview = { lines: ['Ada'], tailoring: { matched: [], missing: [] }, ats: { format: 'docx', passes: true, issues: [] } }
  let saved: Record<string, unknown> | undefined
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.endsWith('/api/saved-documents') && init?.method === 'POST') {
      saved = JSON.parse(String(init.body))
      return new Response(JSON.stringify({ id: 'd1', label: 'x', template: 'resume-classic', format: 'docx', filename: 'a.docx', created_at: '2026-11-14T10:00:00Z', ats_issues: [] }), { status: 201 })
    }
    const body = u.includes('templates') ? [template] : u.includes('profile') ? profile : u.includes('preview') ? preview : []
    return new Response(JSON.stringify(body))
  }))
  renderApp(<NewDocumentScreen />)
  const next = () => fireEvent.click(screen.getByRole('button', { name: /^Next/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Python engineer' } })
  next()
  await screen.findByText('Classic resume')
  fireEvent.change(screen.getByLabelText(/role/i), { target: { value: 'Engineer' } })
  fireEvent.change(screen.getByLabelText(/company/i), { target: { value: 'Acme' } })
  next()
  fireEvent.click(await screen.findByLabelText('SQL')) // untick one skill
  await waitFor(() => expect(screen.getByRole('button', { name: /^Next/ })).toBeEnabled())
  next()
  await screen.findByText('Ada')
  fireEvent.click(screen.getByRole('button', { name: 'Done' }))
  await waitFor(() => expect(saved).toBeDefined())
  expect(saved).toMatchObject({
    template: 'resume-classic', format: 'docx', label: 'Engineer · Acme',
    skill_ids: ['s1'], education_ids: ['e1'], selection: ['b1'], overrides: {},
  })
})
