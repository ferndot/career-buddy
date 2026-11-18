import { Box, Button, IconButton, Progress, Text } from '@chakra-ui/react'
import type { CSSProperties } from 'react'
import { LuArrowLeft, LuScrollText, LuX } from 'react-icons/lu'
import { ActivityLog, clock, StatusBadge } from './ActivityLog'
import { useActivityActions, useActivityPanel, type Activity } from './activityStore'
import { ResizeHandle } from './ResizeHandle'
import { useResizableWidth } from './useResizableWidth'

/** The header button that shows or hides the sidebar. */
export function LogsButton() {
  const { open } = useActivityPanel()
  const { toggle } = useActivityActions()
  return (
    <IconButton aria-label="Logs" aria-pressed={open} size="sm" variant="ghost" color="app.text3" _hover={{ bg: 'app.hover', color: 'app.text' }} onClick={toggle}>
      <LuScrollText />
    </IconButton>
  )
}

function Row({ activity, onOpen }: { activity: Activity; onOpen: () => void }) {
  const last = activity.entries.at(-1)
  return (
    <Box as="button" onClick={onOpen} display="flex" alignItems="center" gap="2" w="full" textAlign="left" px="3" py="2" borderRadius="md" borderWidth="1px" borderColor="app.border" bg="app.surface2" cursor="pointer" _hover={{ bg: 'app.hover' }}>
      <Text flex="1" minW="0" fontSize="sm" fontWeight="medium" color="app.text" truncate>
        {activity.title}
      </Text>
      <StatusBadge status={activity.status} label={activity.statusLabel} />
      {last && (
        <Text fontSize="xs" color="app.muted" flexShrink={0}>
          {clock(last.at)}
        </Text>
      )}
    </Box>
  )
}

function Stream({ activity }: { activity: Activity }) {
  const { progress, step, error } = activity
  return (
    <ActivityLog key={activity.id} title={activity.title} status={activity.status} statusLabel={activity.statusLabel} entries={activity.entries}>
      {progress !== undefined && (
        <Progress.Root value={progress} max={100} size="sm" aria-label={`Progress of ${activity.title}`}>
          <Progress.Track bg="app.hover" borderRadius="full">
            <Progress.Range bg="app.primary" />
          </Progress.Track>
        </Progress.Root>
      )}
      {step && (
        <Text fontSize="sm" color="app.muted" mt="1.5">
          {step}
        </Text>
      )}
      {error && (
        <Text role="alert" fontSize="sm" color="app.missText" mt="2">
          {error}
        </Text>
      )}
    </ActivityLog>
  )
}

function Panel() {
  const { activities, selected } = useActivityPanel()
  const { close, select } = useActivityActions()
  const size = useResizableWidth()
  const { width } = size
  const current = activities.find((a) => a.id === selected)
  return (
    <Box
      as="aside"
      aria-label="Activity"
      display="flex"
      flexDirection="column"
      minW="0"
      p="4"
      bg="app.surface"
      borderColor="app.border"
      borderWidth="0 0 0 1px"
      flexShrink={0}
      // Always beside the page: a column that takes its width out of the content and stays in view.
      w="var(--log-width)"
      position="sticky"
      top="0"
      h="100vh"
      style={{ '--log-width': `${width}px` } as CSSProperties}
    >
      <ResizeHandle label="Resize log" size={size} />
      <Box display="flex" alignItems="center" gap="2" mb="3">
        {current && (
          <Button size="xs" variant="ghost" color="app.link" onClick={() => select(null)} aria-label="Back to all activities">
            <LuArrowLeft />
          </Button>
        )}
        <Text flex="1" fontWeight="semibold" color="app.text">
          Logs
        </Text>
        <Button size="xs" variant="ghost" color="app.link" onClick={close} aria-label="Close log">
          <LuX />
        </Button>
      </Box>
      {current ? (
        <Stream activity={current} />
      ) : activities.length === 0 ? (
        <Text color="app.muted" fontSize="sm">
          No activity yet
        </Text>
      ) : (
        <Box display="flex" flexDirection="column" gap="2" overflowY="auto" role="list" aria-label="Activities">
          {activities.map((a) => (
            <Box key={a.id} role="listitem">
              <Row activity={a} onOpen={() => select(a.id)} />
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}

/** Every agent activity of the app, on the right of the page, resizable. Closed until the Logs button opens it. */
export function ActivitySidebar() {
  return useActivityPanel().open ? <Panel /> : null
}
