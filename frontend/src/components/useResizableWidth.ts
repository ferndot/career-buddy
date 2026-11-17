import { useCallback, useEffect, useState, type KeyboardEvent, type PointerEvent } from 'react'

export const MIN_WIDTH = 240
export const DEFAULT_WIDTH = 384
export const KEY_STEP = 24
const STORAGE_KEY = 'career-buddy.sourceLogWidth'

/** Between 240px and 60% of the viewport (never below the minimum, however narrow the viewport). */
export const clampWidth = (width: number, viewport: number) =>
  Math.min(Math.max(width, MIN_WIDTH), Math.max(MIN_WIDTH, Math.round(viewport * 0.6)))

function stored(): number {
  try {
    const n = Number(localStorage.getItem(STORAGE_KEY))
    return Number.isFinite(n) && n > 0 ? n : DEFAULT_WIDTH
  } catch {
    return DEFAULT_WIDTH
  }
}

/** Width of a panel whose drag handle is on its left edge: dragging left widens it. Remembered in localStorage when it can be. */
export function useResizableWidth() {
  const [width, setWidth] = useState(() => clampWidth(stored(), window.innerWidth))
  const [drag, setDrag] = useState<{ x: number; width: number } | null>(null)
  const set = useCallback((w: number) => setWidth(clampWidth(w, window.innerWidth)), [])
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(width))
    } catch {
      /* storage blocked: the width just is not remembered */
    }
  }, [width])
  const handle = {
    onPointerDown: (e: PointerEvent<HTMLElement>) => {
      e.currentTarget.setPointerCapture?.(e.pointerId)
      setDrag({ x: e.clientX, width })
    },
    onPointerMove: (e: PointerEvent<HTMLElement>) => drag && set(drag.width + drag.x - e.clientX),
    onPointerUp: () => setDrag(null),
    onPointerCancel: () => setDrag(null),
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      const dir = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : 0
      if (!dir) return
      e.preventDefault()
      set(width + dir * KEY_STEP)
    },
  }
  return { width, handle, max: Math.max(MIN_WIDTH, Math.round(window.innerWidth * 0.6)) }
}
