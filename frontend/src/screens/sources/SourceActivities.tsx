import { useEffect } from 'react'
import { useActivityActions, type ActivityEntry } from '../../components'
import { useSourceLog, type LogLine } from './sourceLogApi'
import { displayName } from './sourceDisplay'
import { isBusy, useSources, type Source } from './sourcesApi'
import { ACTIVITY } from './StatusBadge'

export const sourceActivityId = (source: string) => `source:${source}`

const LEVEL: Record<string, ActivityEntry['level']> = { WARNING: 'warn', ERROR: 'error', CRITICAL: 'error', DEBUG: 'debug' }
const entry = (l: LogLine): ActivityEntry => ({ id: l.seq, at: l.time, level: LEVEL[l.level] ?? 'info', text: l.message, title: l.logger })

/** Puts one source in the activity store while it has log lines, is working or failed to load: its status, progress and step, and the server's log lines. Gone with the source. */
function SourceActivity({ source }: { source: Source }) {
  const { set, remove } = useActivityActions()
  const { data, isError } = useSourceLog(source.source, isBusy(source))
  const id = sourceActivityId(source.source)
  const shown = ACTIVITY[data?.status ?? source.status]
  const progress = data?.progress ?? source.progress
  const step = data?.step ?? source.step
  const shownInLog = (data?.lines.length ?? 0) > 0 || isBusy(source) || isError // a source with nothing to say is not listed
  useEffect(() => {
    if (!shownInLog) return remove(id)
    set({
      id,
      title: displayName(source.source),
      status: shown.status,
      statusLabel: shown.label,
      entries: (data?.lines ?? []).map(entry),
      progress,
      step,
      error: isError ? 'Could not load the log.' : undefined,
    })
  }, [set, remove, id, source.source, shown.status, shown.label, data?.lines, progress, step, isError, shownInLog])
  useEffect(() => () => remove(id), [remove, id])
  return null
}

/** Every source is an activity, from any page: mounted once in the app shell. */
export function SourceActivities() {
  const { data: sources = [] } = useSources()
  return (
    <>
      {sources.map((s) => (
        <SourceActivity key={s.source} source={s} />
      ))}
    </>
  )
}
