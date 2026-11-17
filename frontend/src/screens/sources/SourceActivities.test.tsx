import { act, fireEvent, screen, within } from '@testing-library/react'
import { queryClient } from '../../api'
import { openLogs, renderShell } from '../../test/render'
import { SourcesScreen } from './SourcesScreen'
import { LOG_POLL_MS } from './sourceLogApi'

const source = (over: object = {}) => ({
  source: 'resume.pdf', facts: 0, status: 'processing', progress: 30, step: 'Extracting positions', error: null, ...over,
})
const line = (seq: number, message: string, level = 'INFO') => ({
  seq, time: '2026-01-01T10:00:0' + seq + 'Z', level, logger: 'career_buddy.extraction.pipeline', message,
})
const log = (lines: ReturnType<typeof line>[], over: object = {}) => ({
  lines, cursor: lines.at(-1)?.seq ?? 0, run: 1, status: 'processing', progress: 30, step: 'Extracting positions', error: null, ...over,
})

/** The backend: the sources list, and each source's log from `logs` (a reply per request). */
function stubApi(sources: object[], logs: (source: string, call: number) => object, urls: string[] = []) {
  const calls: Record<string, number> = {}
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const m = /\/api\/sources\/([^/]+)\/log/.exec(url)
    if (!m) return new Response(JSON.stringify(sources))
    urls.push(url)
    const name = decodeURIComponent(m[1])
    calls[name] = (calls[name] ?? 0) + 1
    return new Response(JSON.stringify(logs(name, calls[name])))
  }))
}
const show = async (name: string | RegExp) => {
  openLogs()
  fireEvent.click(await screen.findByRole('button', { name }))
}

beforeEach(() => queryClient.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('sources in the activity sidebar', () => {
  it('lists every source as an activity from any page, with the progress, the step and the log lines, warnings marked', async () => {
    stubApi([source(), source({ source: 'cv.docx', status: 'ready', progress: 100, step: 'Parsed' })], (name) =>
      name === 'resume.pdf'
        ? log([line(1, 'chunk 1: asking the model about 900 characters'), line(2, 'the model listed no entities', 'WARNING')])
        : log([line(1, 'old run')], { status: 'ready', progress: 100, step: 'Parsed' }),
    )
    renderShell(<p>Not the sources page</p>)
    openLogs()
    const list = within(await screen.findByRole('list', { name: 'Activities' }))
    expect(await list.findByRole('button', { name: /resume\.pdf.*Working/ })).toBeInTheDocument()
    expect(list.getByRole('button', { name: /cv\.docx.*Parsed/ })).toBeInTheDocument()
    fireEvent.click(list.getByRole('button', { name: /resume\.pdf/ }))
    expect(await screen.findByText(/chunk 1: asking the model/)).toBeInTheDocument()
    expect(screen.getByLabelText('Progress of resume.pdf')).toBeInTheDocument()
    expect(screen.getByText('Extracting positions')).toBeInTheDocument()
    expect(screen.getByText(/the model listed no entities/).closest('[data-level]')).toHaveAttribute('data-level', 'warn')
  })

  it('does not list a source that has nothing logged and is not working', async () => {
    stubApi([source({ status: 'ready', progress: 100, step: 'Parsed' })], () => log([], { status: 'ready', progress: 100, step: 'Parsed' }))
    renderShell(<p>x</p>)
    openLogs()
    expect(await screen.findByText('No activity yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /resume.pdf/ })).not.toBeInTheDocument()
  })

  it('polls with the cursor while processing and stops once the log says it is done', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const urls: string[] = []
    stubApi([source()], (_, call) => (call === 1 ? log([line(1, 'first')]) : log([line(2, 'second')], { status: 'ready', progress: 100, step: 'Parsed' })), urls)
    renderShell(<p>x</p>)
    await show(/resume\.pdf/)
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
    const urls: string[] = []
    stubApi([source({ status: 'ready', progress: 100 })], () => log([line(1, 'old run')], { status: 'ready', progress: 100, step: 'Parsed' }), urls)
    renderShell(<p>x</p>)
    await show(/resume\.pdf/)
    expect(await screen.findByText(/old run/)).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(LOG_POLL_MS * 3))
    expect(urls).toHaveLength(1)
  })

  it('opens the source stream from the Log button of its card on the Sources page', async () => {
    stubApi([source({ status: 'ready', progress: 100 })], () => log([line(1, 'old run')], { status: 'ready', progress: 100, step: 'Parsed' }))
    renderShell(<SourcesScreen />)
    fireEvent.click(await screen.findByRole('button', { name: 'Show log of resume.pdf' }))
    expect(await screen.findByText(/old run/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show log of resume.pdf' })).toHaveAttribute('aria-pressed', 'true')
  })
})
