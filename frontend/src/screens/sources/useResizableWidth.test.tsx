import { fireEvent, screen } from '@testing-library/react'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { SourceLogSidebar } from './SourceLogSidebar'
import { clampWidth, DEFAULT_WIDTH, KEY_STEP, MIN_WIDTH } from '../../components/useResizableWidth'

describe('clampWidth', () => {
  it('keeps the width between 240px and 60% of the viewport', () => {
    expect(clampWidth(100, 1200)).toBe(MIN_WIDTH)
    expect(clampWidth(400, 1200)).toBe(400)
    expect(clampWidth(900, 1200)).toBe(720)
    expect(clampWidth(500, 300)).toBe(MIN_WIDTH) // a viewport too narrow for the minimum
  })
})

describe('the log sidebar resize handle', () => {
  beforeEach(() => {
    queryClient.clear()
    localStorage.clear()
    window.innerWidth = 1000
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ lines: [], cursor: 0, run: 1, status: 'ready', progress: 100, step: '', error: null }))))
  })
  afterEach(() => vi.unstubAllGlobals())
  const source = { source: 'a.txt', facts: 1, status: 'ready' as const, progress: 100, step: '', error: null }

  it('resizes with the arrow keys, within the limits, and remembers the width', () => {
    renderApp(<SourceLogSidebar source={source} onClose={() => {}} />)
    const handle = screen.getByLabelText('Resize log')
    expect(handle).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH))
    fireEvent.keyDown(handle, { key: 'ArrowLeft' }) // the handle is on the left edge: left widens
    expect(handle).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH + KEY_STEP))
    fireEvent.keyDown(handle, { key: 'ArrowRight' })
    fireEvent.keyDown(handle, { key: 'ArrowRight' })
    expect(handle).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH - KEY_STEP))
    for (let i = 0; i < 40; i++) fireEvent.keyDown(handle, { key: 'ArrowLeft' })
    expect(handle).toHaveAttribute('aria-valuenow', '600') // 60% of 1000
    expect(localStorage.getItem('career-buddy.sourceLogWidth')).toBe('600')
    for (let i = 0; i < 40; i++) fireEvent.keyDown(handle, { key: 'ArrowRight' })
    expect(handle).toHaveAttribute('aria-valuenow', String(MIN_WIDTH))
  })

  it('resizes by dragging', () => {
    renderApp(<SourceLogSidebar source={source} onClose={() => {}} />)
    const handle = screen.getByLabelText('Resize log')
    fireEvent.pointerDown(handle, { clientX: 500, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 450, pointerId: 1 })
    expect(handle).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH + 50))
    fireEvent.pointerUp(handle, { pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 100, pointerId: 1 })
    expect(handle).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH + 50)) // not dragging any more
  })

  it('starts from the remembered width', () => {
    localStorage.setItem('career-buddy.sourceLogWidth', '500')
    renderApp(<SourceLogSidebar source={source} onClose={() => {}} />)
    expect(screen.getByLabelText('Resize log')).toHaveAttribute('aria-valuenow', '500')
  })
})
