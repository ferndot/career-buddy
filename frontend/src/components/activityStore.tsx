import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { ActivityEntry, ActivityStatus } from './ActivityLog'

export const MAX_ENTRIES = 200

/** Records one entry; `status`, when given, replaces the activity's status. */
export type Log = (level: ActivityEntry['level'], text: string, status?: ActivityStatus) => void

/** One independent piece of agent work: a posting review, a document being written, a source being read. */
export type Activity = {
  id: string
  title: string
  status: ActivityStatus
  /** Replaces the badge's wording, for a status the owner names differently. */
  statusLabel?: string
  /** Oldest first, newest last. */
  entries: ActivityEntry[]
  /** A progress bar above the entries; null is an unmeasurable step. Absent: no bar. */
  progress?: number | null
  step?: string
  error?: string
}

type Panel = { activities: Activity[]; open: boolean; selected: string | null }
type Actions = {
  write: (id: string, title: string, level: ActivityEntry['level'], text: string, status?: ActivityStatus) => void
  /** Adds the activity or replaces it whole: for work whose lines come from somewhere else (the server's source logs). */
  set: (activity: Activity) => void
  remove: (id: string) => void
  toggle: () => void
  close: () => void
  /** The entry whose stream is shown; null shows the list. */
  select: (id: string | null) => void
  /** Opens the sidebar on one activity's stream. */
  show: (id: string) => void
}

const PanelContext = createContext<Panel | null>(null)
const ActionsContext = createContext<Actions | null>(null)

const put = (list: Activity[], next: Activity) => (list.some((a) => a.id === next.id) ? list.map((a) => (a.id === next.id ? next : a)) : [...list, next])

/** Every activity of the app, in memory, so work started on one page shows from any page. Mounted once at the root. */
export function ActivityProvider({ children }: { children: ReactNode }) {
  const [panel, setPanel] = useState<Panel>({ activities: [], open: false, selected: null })
  const actions = useMemo<Actions>(
    () => ({
      write: (id, title, level, text, status) =>
        setPanel((p) => {
          const cur = p.activities.find((a) => a.id === id) ?? { id, title, status: 'idle' as const, entries: [] }
          const entries = [...cur.entries, { at: Date.now(), level, text }].slice(-MAX_ENTRIES)
          return { ...p, activities: put(p.activities, { ...cur, title, status: status ?? cur.status, entries }) }
        }),
      set: (activity) => setPanel((p) => ({ ...p, activities: put(p.activities, activity) })),
      remove: (id) => setPanel((p) => ({ ...p, activities: p.activities.filter((a) => a.id !== id) })),
      toggle: () => setPanel((p) => ({ ...p, open: !p.open })),
      close: () => setPanel((p) => ({ ...p, open: false })),
      select: (id) => setPanel((p) => ({ ...p, selected: id })),
      show: (id) => setPanel((p) => ({ ...p, open: true, selected: id })),
    }),
    [],
  )
  return (
    <ActionsContext.Provider value={actions}>
      <PanelContext.Provider value={panel}>{children}</PanelContext.Provider>
    </ActionsContext.Provider>
  )
}

function need<T>(value: T | null): T {
  if (!value) throw new Error('The activity store is mounted at the app root (ActivityProvider).')
  return value
}

/** The activities and whether the sidebar is open: re-renders on every change. */
export const useActivityPanel = () => need(useContext(PanelContext))

/** The store's actions: stable, so using them never re-renders. */
export const useActivityActions = () => need(useContext(ActionsContext))

let seq = 0

/** `newLog(title)` opens a new activity for one request and returns its `Log`: every run gets its own lines, never shared. */
export function useActivityLog() {
  const { write } = useActivityActions()
  return useCallback(
    (title: string): Log => {
      const id = `${Date.now().toString(36)}-${(seq += 1)}`
      return (level, text, status) => write(id, title, level, text, status)
    },
    [write],
  )
}
