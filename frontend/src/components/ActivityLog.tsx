import { Badge, Box, Heading, Text } from '@chakra-ui/react'
import { useEffect, useRef, type ReactNode } from 'react'

export type ActivityStatus = 'idle' | 'working' | 'done' | 'failed' | 'unavailable'
export type ActivityEntry = {
  /** When it happened: a Date, epoch milliseconds or an ISO string. Shown in local time. */
  at: Date | number | string
  level: 'info' | 'warn' | 'error' | 'debug'
  text: string
  /** A stable key, when the entries come with one; otherwise the position is used. */
  id?: string | number
  /** Shown on hover. */
  title?: string
}

const NEAR_BOTTOM = 24
const BADGE: Record<ActivityStatus, { label: string; bg: string; color: string }> = {
  idle: { label: 'Idle', bg: 'app.hover', color: 'app.muted' },
  working: { label: 'Working', bg: 'app.warnBg', color: 'app.warnText' },
  done: { label: 'Done', bg: 'app.okBg', color: 'app.okText' },
  failed: { label: 'Failed', bg: 'app.missBg', color: 'app.missText' },
  unavailable: { label: 'Unavailable', bg: 'app.hover', color: 'app.muted' },
}
export const clock = (at: ActivityEntry['at']) => new Date(at).toLocaleTimeString([], { hour12: false })

/** The one status label for anything that works in the background. `label` replaces the default wording. */
export function StatusBadge({ status, label }: { status: ActivityStatus; label?: string }) {
  const { label: text, ...colors } = BADGE[status]
  return (
    <Badge {...colors} borderRadius="full" px="2" flexShrink={0}>
      {label ?? text}
    </Badge>
  )
}

function Entry({ entry }: { entry: ActivityEntry }) {
  const bad = entry.level === 'warn' || entry.level === 'error'
  return (
    <Box color={bad ? 'app.missText' : entry.level === 'debug' ? 'app.muted' : 'app.text'} bg={bad ? 'app.missBg' : undefined} px="1" title={entry.title} data-level={entry.level}>
      <Text as="span" color="app.muted">
        {clock(entry.at)}{' '}
      </Text>
      {entry.text}
    </Box>
  )
}

type Props = {
  title: string
  status: ActivityStatus
  /** Replaces the badge's wording, for a status the screen names differently. */
  statusLabel?: string
  /** Oldest first, newest last. */
  entries: ActivityEntry[]
  /** Buttons in the header, after the status badge. */
  actions?: ReactNode
  /** Shown between the header and the entries: a progress bar, a step, an error. */
  children?: ReactNode
  /** Names the entries region. */
  logLabel?: string
}

/**
 * What an agent is doing, as a short log: title, status, entries newest last, following the newest until the user scrolls up.
 * It lives in the activity sidebar: on wide screens it fills the height it is given, on phones the entries are capped.
 */
export function ActivityLog({ title, status, statusLabel, entries, actions, children, logLabel = 'Activity log' }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const pinned = useRef(true) // follow the newest entry, until the user scrolls up
  useEffect(() => {
    const el = box.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [entries.length])
  const onScroll = () => {
    const el = box.current
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM
  }
  return (
    <Box as="section" aria-label={`Log of ${title}`} display="flex" flexDirection="column" flex="1" minH="0" minW="0">
      <Box display="flex" alignItems="center" gap="2" mb="2">
        <Heading as="h2" size="sm" flex="1" minW="0" color="app.text" truncate>
          {title}
        </Heading>
        <StatusBadge status={status} label={statusLabel} />
        {actions}
      </Box>
      {children}
      <Box
        ref={box}
        role="log"
        aria-label={logLabel}
        onScroll={onScroll}
        mt="3"
        bg="app.surface2"
        borderRadius="md"
        p="2"
        maxH={{ base: '64', xl: 'none' }}
        flex={{ xl: '1' }}
        minH={{ xl: '0' }}
        overflowY="auto"
        fontFamily="mono"
        fontSize="xs"
        whiteSpace="pre-wrap"
        wordBreak="break-word"
      >
        {entries.length === 0 ? <Text color="app.muted">No activity yet</Text> : entries.map((e, i) => <Entry key={e.id ?? i} entry={e} />)}
      </Box>
    </Box>
  )
}
