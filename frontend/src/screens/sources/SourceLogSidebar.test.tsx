import { act, screen } from '@testing-library/react'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { SourceLogSidebar } from './SourceLogSidebar'
import { LOG_POLL_MS } from './sourceLogApi'
import type { Source } from './sourcesApi'

const source = (over: Partial<Source> = {}): Source => ({
  source: 'resume.pdf', facts: 0, status: 'processing', progress: 30, step: 'Extracting positions', error: null, ...over,
})
const line = (seq: number, message: string, level = 'INFO') => ({
  seq, time: '2026-01-01T10:00:0' + seq + 'Z', level, logger: 'career_buddy.extraction.pipeline', message,
})
const reply = (lines: ReturnType<typeof line>[], over: object = {}) =>
  new Response(JSON.stringify({ lines, cursor: lines.at(-1)?.seq ?? 0, run: 1, status: 'processing', progress: 30, step: 'Extracting positions', error: null, ...over }))

beforeEach(() => queryClient.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('SourceLogSidebar', () => {
  it('shows the progress, the step and the log lines, with warnings marked', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => reply([line(1, 'chunk 1: asking the model about 900 characters'), line(2, 'the model listed no entities', 'WARNING')])))
    renderApp(<SourceLogSidebar source={source()} onClose={() => {}} />)
    expect(await screen.findByText(/chunk 1: asking the model/)).toBeInTheDocument()
    expect(screen.getByText('Extracting positions')).toBeInTheDocument()
    expect(screen.getByText('30%')).toBeInTheDocument()
    expect(screen.getByText(/the model listed no entities/).closest('[data-level]')).toHaveAttribute('data-level', 'WARNING')
    expect(screen.queryByText('No activity yet')).not.toBeInTheDocument()
  })

  it('says so when nothing has been logged', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => reply([], { status: 'ready', progress: 100, step: 'Done' })))
    renderApp(<SourceLogSidebar source={source({ status: 'ready', progress: 100, step: 'Done' })} onClose={() => {}} />)
    expect(await screen.findByText('No activity yet')).toBeInTheDocument()
    expect(screen.getByText('Done', { selector: 'span' })).toBeInTheDocument()
  })

  it('polls with the cursor while processing and stops once the log says it is done', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const urls: string[] = []
    let calls = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      calls += 1
      return calls === 1
        ? reply([line(1, 'first')])
        : reply([line(2, 'second')], { status: 'ready', progress: 100, step: 'Done' })
    }))
    renderApp(<SourceLogSidebar source={source()} onClose={() => {}} />)
    expect(await screen.findByText(/first/)).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(LOG_POLL_MS + 50))
    expect(await screen.findByText(/second/)).toBeInTheDocument()
    expect(screen.getByText(/first/)).toBeInTheDocument() // lines accumulate
    expect(urls).toEqual(['/api/sources/resume.pdf/log?since=0', '/api/sources/resume.pdf/log?since=1'])
    await act(() => vi.advanceTimersByTimeAsync(LOG_POLL_MS * 3))
    expect(urls).toHaveLength(2) // finished: no more polling
  })

  it('does not poll a source that is already finished', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetchMock = vi.fn(async () => reply([line(1, 'old run')], { status: 'ready', progress: 100, step: 'Done' }))
    vi.stubGlobal('fetch', fetchMock)
    renderApp(<SourceLogSidebar source={source({ status: 'ready', progress: 100 })} onClose={() => {}} />)
    expect(await screen.findByText(/old run/)).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(LOG_POLL_MS * 3))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
