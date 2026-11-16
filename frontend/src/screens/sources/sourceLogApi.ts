import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, endpoints } from '../../api'
import type { SourceStatus } from './sourcesApi'

export type LogLine = { seq: number; time: string; level: string; logger: string; message: string }

export type SourceLog = {
  lines: LogLine[]
  cursor: number
  /** Changes when a new run starts: the lines held from the earlier run are dropped. */
  run: number
  status: SourceStatus
  progress: number | null
  step: string
  error: string | null
}

export const LOG_POLL_MS = 1000
const MAX_LINES = 500 // the server keeps no more per source either
const inFlight = (status?: SourceStatus) => status === 'queued' || status === 'processing'

/** The log of one source, fetched incrementally (`since` cursor) and polled only while it is queued or processing. */
export function useSourceLog(source: string | null, busy: boolean) {
  const qc = useQueryClient()
  const key = ['sources', 'log', source]
  return useQuery({
    queryKey: key,
    enabled: source !== null,
    staleTime: 0,
    queryFn: async (): Promise<SourceLog> => {
      const held = qc.getQueryData<SourceLog>(key)
      const next = await apiFetch<SourceLog>(`${endpoints.sources.log(source!)}?since=${held?.cursor ?? 0}`)
      if (!held || held.run !== next.run) return next
      return { ...next, lines: [...held.lines, ...next.lines].slice(-MAX_LINES) }
    },
    // Once the log has answered, its own status decides (it holds the final lines); the list's word only starts polling.
    refetchInterval: (q) => ((q.state.data ? inFlight(q.state.data.status) : busy) ? LOG_POLL_MS : false),
  })
}
