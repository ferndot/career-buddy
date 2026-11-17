// Test helper: answers POST /api/fit like the backend does, on top of whatever fetch stub is already installed (see wizardStub).
import { vi } from 'vitest'
import type { Fit } from '../documents/api'

const NO_MODEL = { detail: 'Connect a model in Settings to check the job posting for requirements.', code: 'llm_unavailable' }

/** `answer` is the review, `'unavailable'` for the 503 the backend gives when no model is connected, or `'error'` for any other failure (500). `hold` keeps the answer back until it resolves. Returns the posted bodies. */
export function stubReview(answer: Partial<Fit> | 'unavailable' | 'error', hold?: Promise<void>): Record<string, unknown>[] {
  const posted: Record<string, unknown>[] = []
  const inner = globalThis.fetch
  const empty: Fit = { title: '', company: '', must_have: [], nice_to_have: [], missing_must_have: [], missing_nice_to_have: [] }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (!String(url).endsWith('/api/fit')) return inner(url, init)
    posted.push(JSON.parse(String(init?.body)))
    await hold
    if (answer === 'error') return new Response(JSON.stringify({ detail: 'boom' }), { status: 500 })
    return answer === 'unavailable'
      ? new Response(JSON.stringify(NO_MODEL), { status: 503 })
      : new Response(JSON.stringify({ ...empty, ...answer }))
  }))
  return posted
}
