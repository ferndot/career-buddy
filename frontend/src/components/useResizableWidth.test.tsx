import { fireEvent, screen } from '@testing-library/react'
import { queryClient } from '../api'
import { openLogs, renderShell } from '../test/render'
import { clampWidth, DEFAULT_WIDTH, KEY_STEP, MIN_WIDTH } from './useResizableWidth'

describe('clampWidth', () => {
  it('keeps the width between 240px and 60% of the viewport', () => {
    expect(clampWidth(100, 1200)).toBe(MIN_WIDTH)
    expect(clampWidth(400, 1200)).toBe(400)
    expect(clampWidth(900, 1200)).toBe(720)
    expect(clampWidth(500, 300)).toBe(MIN_WIDTH) // a viewport too narrow for the minimum
  })
})

describe('the activity sidebar resize handle', () => {
  beforeEach(() => {
    queryClient.clear()
    localStorage.clear()
    window.innerWidth = 1000
    vi.stubGlobal('fetch', vi.fn(async () => new Response('[]')))
  })
  afterEach(() => vi.unstubAllGlobals())
  const open = () => {
    renderShell(<p>The page</p>)
    openLogs()
  }

  it('resizes with the arrow keys, within the limits, and remembers the width', () => {
    open()
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
    open()
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
    open()
    expect(screen.getByLabelText('Resize log')).toHaveAttribute('aria-valuenow', '500')
  })
})
