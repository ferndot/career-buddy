import { screen } from '@testing-library/react'
import { renderApp } from '../../test/render'
import { SourcesScreen } from './SourcesScreen'

const sources = [
  { source: 'resume.pdf', facts: 8, status: 'processing', progress: 62, step: 'Step 2 of 3: 5 of 8 positions read', error: null },
  { source: 'linkedin-export', facts: 14, status: 'ready', progress: 100, step: '', error: null },
  { source: 'notes.txt', facts: 0, status: 'failed', progress: 0, step: '', error: 'Model unreachable' },
]

describe('SourcesScreen', () => {
  it('shows progress, source cards and failed errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(sources))))
    renderApp(<SourcesScreen />)
    expect(await screen.findByText('Processing 62%')).toBeInTheDocument()
    expect(screen.getByText('Step 2 of 3: 5 of 8 positions read')).toBeInTheDocument()
    expect(screen.getByText('LinkedIn export')).toBeInTheDocument()
    expect(screen.getByText('Model unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry notes.txt' })).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
