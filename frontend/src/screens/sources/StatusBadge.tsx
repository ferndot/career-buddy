import { StatusBadge as Badge, type ActivityStatus } from '../../components'
import type { SourceStatus } from './sourcesApi'

/** A source's status in the shared activity vocabulary, with the wording sources use. */
export const ACTIVITY: Record<SourceStatus, { status: ActivityStatus; label: string }> = {
  queued: { status: 'working', label: 'Working' },
  processing: { status: 'working', label: 'Working' },
  ready: { status: 'done', label: 'Parsed' },
  failed: { status: 'failed', label: 'Failed' },
}

/** The one status label for a source, in the same place on every card. */
export const StatusBadge = ({ status }: { status: SourceStatus }) => <Badge {...ACTIVITY[status]} />
