import { Badge, Box, Heading, Text } from '@chakra-ui/react'
import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import { MIN_WIDTH, useResizableWidth } from './useResizableWidth'

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
const clock = (at: ActivityEntry['at']) => new Date(at).toLocaleTimeString([], { hour12: false })

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
  /** Wide screens: a resizable panel fixed to the full viewport height at the right. Otherwise an ordinary card. */
  docked?: boolean
}

function Content({ title, status, statusLabel, entries, actions, children, logLabel = 'Activity log', docked }: Props) {
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
    <>
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
        maxH={docked ? { base: '64', xl: 'none' } : '64'}
        flex={docked ? { xl: '1' } : undefined}
        minH={docked ? { xl: '0' } : undefined}
        overflowY="auto"
        fontFamily="mono"
        fontSize="xs"
        whiteSpace="pre-wrap"
        wordBreak="break-word"
      >
        {entries.length === 0 ? <Text color="app.muted">No activity yet</Text> : entries.map((e, i) => <Entry key={e.id ?? i} entry={e} />)}
      </Box>
    </>
  )
}

const panel = { bg: 'app.surface', borderColor: 'app.border', p: '4', display: 'flex', flexDirection: 'column', minW: '0' } as const

function Docked(props: Props) {
  const { width, handle, max } = useResizableWidth()
  return (
    // The wrapper keeps the panel's room in the page flow; the panel itself is fixed on wide screens.
    <Box w={{ base: 'full', xl: 'var(--log-width)' }} flexShrink={0} minW="0" style={{ '--log-width': `${width}px` } as CSSProperties}>
      <Box
        as="aside"
        aria-label={`Log of ${props.title}`}
        {...panel}
        borderWidth={{ base: '1px', xl: '0 0 0 1px' }}
        borderRadius={{ base: 'lg', xl: 'none' }}
        position={{ base: 'relative', xl: 'fixed' }}
        w={{ base: 'full', xl: 'var(--log-width)' }}
        top={{ xl: '0' }}
        right={{ xl: '0' }}
        h={{ xl: '100vh' }}
        zIndex={{ xl: 'docked' }}
      >
        <Box
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize log"
          aria-valuenow={width}
          aria-valuemin={MIN_WIDTH}
          aria-valuemax={max}
          tabIndex={0}
          {...handle}
          display={{ base: 'none', xl: 'block' }}
          position="absolute"
          left="-3px"
          top="0"
          bottom="0"
          w="6px"
          cursor="col-resize"
          touchAction="none"
          borderRadius="full"
          _hover={{ bg: 'app.borderStrong' }}
          _focusVisible={{ bg: 'app.primary', outline: 'none' }}
        />
        <Content {...props} docked />
      </Box>
    </Box>
  )
}

/**
 * What an agent is doing, as a short log: title, status, entries newest last, optional actions.
 * Put it in a flex container that is a column on phones and a row on wide screens; `docked` pins it to the right edge instead (Sources).
 */
export function ActivityLog(props: Props) {
  if (props.docked) return <Docked {...props} />
  return (
    <Box as="aside" aria-label={`Log of ${props.title}`} {...panel} borderWidth="1px" borderRadius="lg" w={{ base: 'full', xl: '80' }} flexShrink={0}>
      <Content {...props} />
    </Box>
  )
}
