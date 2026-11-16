import { Badge, Box, Progress, Text } from '@chakra-ui/react'
import { displayName } from './sourceDisplay'
import type { Source } from './sourcesApi'

/** One card for the first source still in flight; the badge shows its percentage. */
export function ProcessingCard({ sources }: { sources: Source[] }) {
  const s = sources.find((x) => x.status === 'processing') ?? sources[0]
  const name = displayName(s.source)
  const more = sources.length - 1
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.primary" borderRadius="lg" px="5" py="4" mb="3">
      <Box display="flex" alignItems="center" gap="3" flexWrap="wrap">
        <Box flex="1" minW="0">
          <Text fontWeight="semibold" fontSize="sm" color="app.text" truncate>
            {name}
          </Text>
          <Text fontSize="sm" color="app.muted">
            AI is reading positions, bullets and skills{more > 0 ? ` (+${more} waiting)` : ''}
          </Text>
        </Box>
        <Badge bg="app.warnBg" color="app.warnText" borderRadius="full" px="2">
          {s.status === 'queued' ? 'Queued' : `Processing ${s.progress}%`}
        </Badge>
      </Box>
      <Progress.Root value={s.progress} max={100} mt="3" size="sm" aria-label={`Processing ${name}`}>
        <Progress.Track bg="app.hover" borderRadius="full">
          <Progress.Range bg="app.primary" />
        </Progress.Track>
      </Progress.Root>
      {s.step && (
        <Text fontSize="sm" color="app.muted" mt="1.5">
          {s.step}
        </Text>
      )}
    </Box>
  )
}
