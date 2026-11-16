import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { NewDocumentScreen } from './NewDocumentScreen'

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

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
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 2 of 5 · Documents')
  unmount()
  renderApp(<NewDocumentScreen />)
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 1 of 5 · Job posting')
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

test('first step shows a decorative mascot that stops moving under reduced motion', () => {
  const { container, unmount } = renderApp(<NewDocumentScreen />)
  const mascot = container.querySelector('svg[data-mascot]')
  expect(mascot).toHaveAttribute('aria-hidden', 'true')
  expect(mascot).toHaveClass('cb-anim')
  unmount()
  const real = window.matchMedia
  window.matchMedia = (q: string) => ({ ...real(q), matches: q.includes('reduce') }) as MediaQueryList
  try {
    const { container: still } = renderApp(<NewDocumentScreen />)
    expect(still.querySelector('svg[data-mascot]')).not.toHaveClass('cb-anim')
  } finally {
    window.matchMedia = real
  }
})
