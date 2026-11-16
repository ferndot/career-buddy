import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { renderApp } from '../../test/render'
import { NewDocumentScreen } from './NewDocumentScreen'

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

test('starts on the job posting step with the wizard footer', () => {
  renderApp(<NewDocumentScreen />)
  expect(screen.getByRole('heading', { name: 'New document' })).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Wizard steps' })).toBeInTheDocument()
  expect(screen.getByLabelText('Or paste the job posting')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Next/ })).toBeEnabled()
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
