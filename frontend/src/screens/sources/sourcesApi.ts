import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, endpoints } from '../../api'

export type SourceStatus = 'queued' | 'processing' | 'ready' | 'failed'

export type Source = {
  source: string
  facts: number
  status: SourceStatus
  progress: number | null  // null while the current step has no measurable progress
  step: string
  error: string | null
}

const KEY = ['sources']
const reindexPath = (source: string) => `${endpoints.sources.remove(source)}/reindex`
export const isBusy = (s: Source) => s.status === 'queued' || s.status === 'processing'

/** Polls every 1.5s while any source is still queued or processing. */
export function useSources() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiFetch<Source[]>(endpoints.sources.list()),
    refetchInterval: (q) => (q.state.data?.some(isBusy) ? 1500 : false),
  })
}

// Every write refetches the list, so both 202 (record) and 200 ({facts}) import replies are handled.
function useRefreshing<V>(fn: (v: V) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSettled: () => qc.invalidateQueries({ queryKey: KEY }) })
}

export const useRemoveSource = () =>
  useRefreshing((source: string) => apiFetch(endpoints.sources.remove(source), { method: 'DELETE' }))

export const useReindexSources = () =>
  useRefreshing((sources: string[]) =>
    Promise.allSettled(sources.map((s) => apiFetch(reindexPath(s), { method: 'POST' }))),
  )

export type NewSource = { kind: 'file'; file: File } | { kind: 'text'; name: string; text: string }

export const useImportSource = () =>
  useRefreshing((s: NewSource) => {
    if (s.kind === 'text') {
      return apiFetch(endpoints.imports.text(), { method: 'POST', body: { text: s.text, source: s.name } })
    }
    const form = new FormData()
    form.append('file', s.file)
    return apiFetch(endpoints.imports.file(), { method: 'POST', body: form })
  })
