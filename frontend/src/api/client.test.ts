import { ApiError, apiFetch } from './client'

afterEach(() => vi.unstubAllGlobals())

const stubFetch = (res: Response) => {
  const fn = vi.fn().mockResolvedValue(res)
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('apiFetch', () => {
  it('throws ApiError with status and parsed body on 404', async () => {
    stubFetch(new Response(JSON.stringify({ detail: 'nope' }), { status: 404, statusText: 'Not Found' }))
    const err = await apiFetch('/api/missing').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 404, body: { detail: 'nope' } })
  })

  it('sends JSON and returns parsed body', async () => {
    const fn = stubFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    await expect(apiFetch('/api/x', { method: 'POST', body: { a: 1 } })).resolves.toEqual({ ok: true })
    const [url, init] = fn.mock.calls[0]
    expect(url).toBe('/api/x')
    expect(init.body).toBe('{"a":1}')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })

  it('returns undefined for 204', async () => {
    stubFetch(new Response(null, { status: 204 }))
    await expect(apiFetch('/api/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
