import { fireEvent, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { DocumentDetailScreen } from './DocumentDetailScreen'
import { DocumentsScreen } from './DocumentsScreen'

const doc = { id: 'd1', label: 'Data Platform Engineer · Contoso Data', template: 'resume-classic', filename: 'Data-Platform-Engineer', created_at: '2026-11-14T10:00:00Z', ats_issues: [] }
const layout = { header: 'plain', side: [], css: '', accent: '', panel: '' }
const templates = [{ id: 'resume-classic', kind: 'resume', label: 'Classic resume', formats: ['docx'], required: [], optional: [], sections: [], layout, instructions: '', styles: [], ats_safe: true }]
const html = '<header class="plain"><h1 data-slot="name" data-origin="fact"></h1></header><div class="cols"><div class="main"><h2>Experience</h2><ul><li data-slot="bullet:1"></li></ul></div></div>'
const content = (job_url: string) => ({ html, css: '', slots: { name: 'Jane Doe', 'bullet:1': 'Cut build times by 60%' }, overrides: {}, generated: {}, source: { template: 'resume-classic', job_url } })

function stubApi(job_url: string) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url)
    return new Response(JSON.stringify(u.includes('templates') ? templates : u.endsWith('/content') ? content(job_url) : [doc]))
  }))
}
const app = (route: string) =>
  renderApp(<Routes><Route path="/documents" element={<DocumentsScreen />} /><Route path="/documents/:id" element={<DocumentDetailScreen />} /></Routes>, route)

afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

test('clicking a saved document in the list opens its detail page', async () => {
  stubApi('https://jobs.example.com/p/1')
  app('/documents')
  fireEvent.click(await screen.findByRole('link', { name: doc.label }))
  expect(await screen.findByRole('heading', { name: doc.label })).toBeInTheDocument()
  expect(screen.getByText('Resume · Classic resume')).toBeInTheDocument()
})

test('the detail page shows the listing link and the document preview', async () => {
  stubApi('https://jobs.example.com/p/1')
  app('/documents/d1')
  const link = await screen.findByRole('link', { name: 'https://jobs.example.com/p/1' })
  expect(link).toHaveAttribute('href', 'https://jobs.example.com/p/1')
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  const preview = screen.getByRole('document', { name: `Preview of ${doc.label}` })
  expect(preview).toHaveTextContent('Jane Doe')
  expect(preview).toHaveTextContent('Cut build times by 60%')
  expect(screen.getByRole('button', { name: `Download ${doc.label}` })).toBeInTheDocument()
})

test('with no saved link the page says so and shows no link, and a non-http link is not shown as one', async () => {
  for (const url of ['', 'javascript:alert(1)']) {
    stubApi(url)
    const { unmount } = app('/documents/d1')
    expect(await screen.findByText('No link saved')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /http|javascript/ })).not.toBeInTheDocument()
    unmount()
    queryClient.clear()
  }
})
