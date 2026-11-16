import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { DocumentsScreen } from './DocumentsScreen'

const doc = { id: 'd1', label: 'Engineer · Acme', template: 'resume-classic', format: 'docx', filename: 'resume.docx', created_at: '2026-11-14T10:00:00Z', ats_issues: ['x'], version: 1 }
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

test('shows the empty state with a New document action', async () => {
  stubApi([])
  renderApp(<DocumentsScreen />)
  expect(screen.getByRole('heading', { name: 'Documents' })).toBeInTheDocument()
  expect(await screen.findByText('No documents yet')).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'New document' })).toHaveLength(2) // header and empty state
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

test('a version 1 document downloads as it was saved, with no format menu', async () => {
  const calls = stubApi([doc])
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} }))
  renderApp(<DocumentsScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Download Engineer · Acme' }))
  await waitFor(() => expect(calls).toContain('GET /api/saved-documents/d1/file'))
  expect(screen.queryByRole('menuitem', { name: 'Word' })).not.toBeInTheDocument()
})

test('a version 2 document picks Word, PDF or Text when downloading', async () => {
  const calls = stubApi([{ ...doc, version: 2, format: '', filename: 'resume' }])
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} }))
  renderApp(<DocumentsScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Download Engineer · Acme' }))
  expect(await screen.findByRole('menuitem', { name: 'Word' })).toBeInTheDocument()
  expect(screen.getByRole('menuitem', { name: 'PDF' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('menuitem', { name: 'Text' }))
  await waitFor(() => expect(calls).toContain('GET /api/saved-documents/d1/file?format=txt'))
})

test('deletes through the API', async () => {
  const calls = stubApi([doc])
  renderApp(<DocumentsScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete Engineer · Acme' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(calls).toContain('DELETE /api/saved-documents/d1'))
})
