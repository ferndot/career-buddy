import { useCallback, useState } from 'react'
import type { ActivityEntry, ActivityStatus } from './ActivityLog'

export const MAX_ENTRIES = 200

/** Records one entry; `status`, when given, replaces the log's status. */
export type Log = (level: ActivityEntry['level'], text: string, status?: ActivityStatus) => void

/** A client-side activity log for one screen: newest last, the oldest dropped past 200, held in memory only. */
export function useActivityLog() {
  const [state, setState] = useState<{ entries: ActivityEntry[]; status: ActivityStatus }>({ entries: [], status: 'idle' })
  const log: Log = useCallback(
    (level, text, status) =>
      setState((s) => ({ entries: [...s.entries, { at: Date.now(), level, text }].slice(-MAX_ENTRIES), status: status ?? s.status })),
    [],
  )
  return { ...state, log }
}
