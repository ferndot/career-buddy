import { Box, Button, Heading, Progress, Text } from '@chakra-ui/react'
import { useEffect, useRef, type CSSProperties } from 'react'
import { LuX } from 'react-icons/lu'
import { useSourceLog, type LogLine } from './sourceLogApi'
import { displayName } from './sourceDisplay'
import { isBusy, type Source } from './sourcesApi'
import { MIN_WIDTH, useResizableWidth } from './useResizableWidth'
import { StatusBadge } from './StatusBadge'

const NEAR_BOTTOM = 24
const levelColor = (level: string) =>
  level === 'WARNING' || level === 'ERROR' || level === 'CRITICAL' ? 'app.missText' : level === 'DEBUG' ? 'app.muted' : 'app.text'
const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour12: false })

function Line({ line }: { line: LogLine }) {
  const bad = levelColor(line.level) === 'app.missText'
  return (
    <Box color={levelColor(line.level)} bg={bad ? 'app.missBg' : undefined} px="1" title={line.logger} data-level={line.level}>
      <Text as="span" color="app.muted">
        {clock(line.time)}{' '}
      </Text>
      {line.message}
    </Box>
  )
}

/** Live output of one source's processing: progress, step and the log lines, newest at the bottom.
 * Wide screens: a resizable panel fixed to the full viewport height at the right. Narrow: a card below the list. */
export function SourceLogSidebar({ source, onClose }: { source: Source; onClose: () => void }) {
  const { data, isError } = useSourceLog(source.source, isBusy(source))
  const { width, handle, max } = useResizableWidth()
  const name = displayName(source.source)
  const status = data?.status ?? source.status
  const progress = data?.progress ?? source.progress
  const step = data?.step ?? source.step
  const lines = data?.lines ?? []
  const box = useRef<HTMLDivElement>(null)
  const pinned = useRef(true) // follow the newest line, until the user scrolls up
  useEffect(() => {
    const el = box.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [lines.length])
  const onScroll = () => {
    const el = box.current
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM
  }

  return (
    // The wrapper keeps the panel's room in the page flow; the panel itself is fixed on wide screens.
    <Box w={{ base: 'full', xl: 'var(--log-width)' }} flexShrink={0} minW="0" style={{ '--log-width': `${width}px` } as CSSProperties}>
      <Box
        as="aside"
        aria-label={`Log of ${name}`}
        bg="app.surface"
        borderColor="app.border"
        borderWidth={{ base: '1px', xl: '0 0 0 1px' }}
        borderRadius={{ base: 'lg', xl: 'none' }}
        p="4"
        display="flex"
        flexDirection="column"
        minW="0"
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
        <Box display="flex" alignItems="center" gap="2" mb="2">
          <Heading as="h2" size="sm" flex="1" minW="0" color="app.text" truncate>
            {name}
          </Heading>
          <StatusBadge status={status} />
          <Button size="xs" variant="ghost" color="app.link" onClick={onClose} aria-label="Close log">
            <LuX />
          </Button>
        </Box>
        <Progress.Root value={progress} max={100} size="sm" aria-label={`Progress of ${name}`}>
          <Progress.Track bg="app.hover" borderRadius="full">
            <Progress.Range bg="app.primary" />
          </Progress.Track>
        </Progress.Root>
        {step && (
          <Text fontSize="sm" color="app.muted" mt="1.5">
            {step}
          </Text>
        )}
        {isError && (
          <Text role="alert" fontSize="sm" color="app.missText" mt="2">
            Could not load the log.
          </Text>
        )}
        <Box
          ref={box}
          role="log"
          aria-label="Extraction log"
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
          {lines.length === 0 ? (
            <Text color="app.muted">No activity yet</Text>
          ) : (
            lines.map((line) => <Line key={line.seq} line={line} />)
          )}
        </Box>
      </Box>
    </Box>
  )
}
