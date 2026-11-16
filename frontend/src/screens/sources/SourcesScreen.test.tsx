import { fireEvent, screen } from '@testing-library/react'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { SourcesScreen } from './SourcesScreen'

const sources = [
  { source: 'resume.pdf', facts: 8, status: 'processing', progress: 62, step: 'Step 2 of 3: 5 of 8 positions read', error: null },
  { source: 'cv.docx', facts: 14, status: 'ready', progress: 100, step: '', error: null },
  { source: 'notes.txt', facts: 0, status: 'failed', progress: 0, step: '', error: 'Model unreachable' },
]
const log = (source: string) => ({
  lines: [{ seq: 1, time: '2026-01-01T10:00:00Z', level: 'INFO', logger: 'x', message: `log of ${source}` }],
  cursor: 1, run: 1, status: 'ready', progress: 100, step: 'Done', error: null,
})

function stubApi() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const m = /\/api\/sources\/([^/]+)\/log/.exec(url)
    return new Response(JSON.stringify(m ? log(decodeURIComponent(m[1])) : sources))
  }))
}

beforeEach(() => queryClient.clear())
afterEach(() => vi.unstubAllGlobals())

describe('SourcesScreen', () => {
  it('shows progress, source cards and failed errors', async () => {
    stubApi()
    renderApp(<SourcesScreen />)
    expect(await screen.findByText('Working')).toBeInTheDocument()
    expect(screen.getAllByText('Step 2 of 3: 5 of 8 positions read').length).toBeGreaterThan(0)
    expect(screen.getByText('cv.docx')).toBeInTheDocument()
    expect(screen.getByText('Model unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry notes.txt' })).toBeInTheDocument()
  })

  it('opens the log of the source being processed, then of the one the user picks, and closes it', async () => {
    stubApi()
    renderApp(<SourcesScreen />)
    expect(await screen.findByText('log of resume.pdf')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show log of cv.docx' }))
    expect(await screen.findByText('log of cv.docx')).toBeInTheDocument()
    expect(screen.queryByText('log of resume.pdf')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close log' }))
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })
})
