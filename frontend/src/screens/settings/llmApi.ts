import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiFetch } from '../../api/client'
import { endpoints } from '../../api/endpoints'

export type Provider = {
  id: string
  label: string
  base_url: string
  url_editable: boolean
  needs_key: boolean
  off_device: boolean
  hint: string
}

export type Connection = {
  id: string
  preset: string
  label: string
  base_url: string
  model: string
  key_hint: string | null
  read_only: boolean
  off_device: boolean
  destination: string
}

export type Listing = { active: string | null; connections: Connection[] }
export type TestResult = { ok: boolean; message: string }
export type NewConnection = {
  preset: string
  label?: string
  base_url?: string
  model: string
  api_key?: string
}

const KEY = ['llm', 'connections'] as const

export const useProviders = () =>
  useQuery({ queryKey: ['llm', 'providers'], queryFn: () => apiFetch<Provider[]>(endpoints.llm.providers()) })

export const useConnections = () =>
  useQuery({ queryKey: KEY, queryFn: () => apiFetch<Listing>(endpoints.llm.connections()) })

function useChange<V>(fn: (v: V) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) })
}

export const useCreateConnection = () =>
  useChange((body: NewConnection) => apiFetch(endpoints.llm.connections(), { method: 'POST', body }))
export const useDeleteConnection = () =>
  useChange((id: string) => apiFetch(endpoints.llm.connection(id), { method: 'DELETE' }))
export const useSetActive = () =>
  useChange((id: string | null) => apiFetch(endpoints.llm.active(), { method: 'PUT', body: { id } }))
export const useTestConnection = () =>
  useMutation({ mutationFn: (id: string) => apiFetch<TestResult>(endpoints.llm.test(), { method: 'POST', body: { id } }) })

/** Plain-words message from a FastAPI error body ({detail: string}), else a generic one. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: unknown } | undefined
    if (typeof body?.detail === 'string') return body.detail
  }
  return 'Something went wrong. Please try again.'
}
