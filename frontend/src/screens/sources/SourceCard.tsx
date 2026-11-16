import { Badge, Box, Button, Text } from '@chakra-ui/react'
import { LuRefreshCw, LuTrash2 } from 'react-icons/lu'
import { displayName, factsLabel } from './sourceDisplay'
import { canReindex, type Source } from './sourcesApi'

type Props = { source: Source; onReindex: () => void; onRemove: () => void }

export function SourceCard({ source: s, onReindex, onRemove }: Props) {
  const name = displayName(s.source)
  const failed = s.status === 'failed'
  const verb = failed ? 'Retry' : 'Reindex'
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="3">
      <Box display="flex" alignItems="center" gap="3" flexWrap="wrap">
        <Box flex="1" minW="0">
          <Text fontWeight="semibold" fontSize="sm" color="app.text" truncate>
            {name}
          </Text>
          <Text fontSize="sm" color="app.muted">
            {factsLabel(s.facts)}
          </Text>
        </Box>
        <Badge
          bg={failed ? 'app.missBg' : 'app.okBg'}
          color={failed ? 'app.missText' : 'app.okText'}
          borderRadius="full"
          px="2"
        >
          {failed ? 'Failed' : 'Parsed'}
        </Badge>
        {canReindex(s) && (
          <Button size="sm" variant="ghost" color="app.link" onClick={onReindex} aria-label={`${verb} ${name}`}>
            <LuRefreshCw /> {verb}
          </Button>
        )}
        <Button size="sm" variant="ghost" color="app.link" onClick={onRemove} aria-label={`Remove ${name}`}>
          <LuTrash2 /> Remove
        </Button>
      </Box>
      {failed && s.error && (
        <Text role="alert" fontSize="sm" color="app.missText" bg="app.missBg" borderRadius="md" px="3" py="2" mt="3">
          {s.error}
        </Text>
      )}
    </Box>
  )
}
