import { Badge } from '@chakra-ui/react'
import type { SourceStatus } from './sourcesApi'

const LABEL: Record<SourceStatus, string> = { queued: 'Working', processing: 'Working', ready: 'Parsed', failed: 'Failed' }
const COLOR: Record<SourceStatus, { bg: string; color: string }> = {
  queued: { bg: 'app.warnBg', color: 'app.warnText' },
  processing: { bg: 'app.warnBg', color: 'app.warnText' },
  ready: { bg: 'app.okBg', color: 'app.okText' },
  failed: { bg: 'app.missBg', color: 'app.missText' },
}

/** The one status label for a source, in the same place on every card. */
export function StatusBadge({ status }: { status: SourceStatus }) {
  return (
    <Badge {...COLOR[status]} borderRadius="full" px="2" flexShrink={0}>
      {LABEL[status]}
    </Badge>
  )
}
