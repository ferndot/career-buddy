import { Progress, Text } from '@chakra-ui/react'
import { ActivityLog, type ActivityEntry } from '../../components'
import { useSourceLog, type LogLine } from './sourceLogApi'
import { displayName } from './sourceDisplay'
import { isBusy, type Source } from './sourcesApi'
import { ACTIVITY } from './StatusBadge'

const LEVEL: Record<string, ActivityEntry['level']> = { WARNING: 'warn', ERROR: 'error', CRITICAL: 'error', DEBUG: 'debug' }
const entry = (l: LogLine): ActivityEntry => ({ id: l.seq, at: l.time, level: LEVEL[l.level] ?? 'info', text: l.message, title: l.logger })

/** Live output of one source's processing: progress, step and the log lines, newest at the bottom.
 * Wide screens: a resizable panel fixed to the full viewport height at the right. Narrow: a card below the list. */
export function SourceLogSidebar({ source, onClose }: { source: Source; onClose: () => void }) {
  const { data, isError } = useSourceLog(source.source, isBusy(source))
  const name = displayName(source.source)
  const progress = data?.progress ?? source.progress
  const step = data?.step ?? source.step
  const shown = ACTIVITY[data?.status ?? source.status]
  return (
    <ActivityLog
      docked
      title={name}
      status={shown.status}
      statusLabel={shown.label}
      logLabel="Extraction log"
      entries={(data?.lines ?? []).map(entry)}
      onClose={onClose}
    >
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
    </ActivityLog>
  )
}
