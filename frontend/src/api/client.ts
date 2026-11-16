const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, statusText = '') {
    super(`API ${status}${statusText ? ` ${statusText}` : ''}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export type ApiInit = Omit<RequestInit, 'body'> & {
  /** Plain objects/arrays are JSON-encoded; strings, FormData, Blob etc. pass through untouched. */
  body?: unknown
}

export const apiUrl = (path: string): string => `${BASE_URL}${path}`

const isRawBody = (b: unknown): b is BodyInit =>
  typeof b === 'string' ||
  b instanceof FormData ||
  b instanceof Blob ||
  b instanceof URLSearchParams ||
  b instanceof ArrayBuffer

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

/** JSON fetch against the backend. Returns undefined for empty (e.g. 204) responses. */
export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { body, headers, ...rest } = init
  const h = new Headers(headers)
  h.set('Accept', 'application/json')
  let payload: BodyInit | undefined
  if (body !== undefined) {
    if (isRawBody(body)) payload = body
    else {
      payload = JSON.stringify(body)
      if (!h.has('Content-Type')) h.set('Content-Type', 'application/json')
    }
  }
  const res = await fetch(apiUrl(path), { ...rest, headers: h, body: payload })
  const parsed = await parseBody(res)
  if (!res.ok) throw new ApiError(res.status, parsed, res.statusText)
  return parsed as T
}
