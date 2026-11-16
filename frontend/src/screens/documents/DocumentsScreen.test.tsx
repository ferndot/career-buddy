import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { DocumentsScreen } from './DocumentsScreen'

const doc = { id: 'd1', label: 'Engineer · Acme', template: 'resume-classic', format: 'docx', filename: 'resume.docx', created_at: '2026-11-14T10:00:00Z', ats_issues: ['x'] }
const templates = [{ id: 'resume-classic', kind: 'resume', label: 'Classic resume', formats: ['docx'], required: [], optional: [] }]

function stubApi(list: unknown[]) {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`)
    if (init?.method === 'DELETE') return new Response(null, { status: 204 })
    return new Response(JSON.stringify(String(url).includes('templates') ? templates : list))
  }))
  return calls
}

afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

test('shows the empty state with a Generate action', async () => {
  stubApi([])
  renderApp(<DocumentsScreen />)
  expect(screen.getByRole('heading', { name: 'Documents' })).toBeInTheDocument()
  expect(await screen.findByText('No documents yet')).toBeInTheDocument()
})

test('lists saved documents and filters by type', async () => {
  stubApi([doc])
  renderApp(<DocumentsScreen />)
  expect(await screen.findByText('Engineer · Acme')).toBeInTheDocument()
  expect(screen.getByText('1 warning')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Download Engineer · Acme' })).toBeInTheDocument()
  await screen.findByText('Classic resume')
  fireEvent.change(screen.getByLabelText('Document type'), { target: { value: 'letter' } })
  expect(screen.getByText('No matches')).toBeInTheDocument()
})

test('deletes through the API', async () => {
  const calls = stubApi([doc])
  renderApp(<DocumentsScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete Engineer · Acme' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(calls).toContain('DELETE /api/saved-documents/d1'))
})
