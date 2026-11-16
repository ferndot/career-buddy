import { Box, Button, Heading, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { EmptyState, PageHeader } from '../../components'
import { AddSourceDialog } from './AddSourceDialog'
import { ProcessingCard } from './ProcessingCard'
import { SourceCard } from './SourceCard'
import { canReindex, isBusy, useReindexSources, useRemoveSource, useSources } from './sourcesApi'

export function SourcesScreen() {
  const [adding, setAdding] = useState(false)
  const { data: sources = [], isError } = useSources()
  const reindex = useReindexSources()
  const remove = useRemoveSource()
  const busy = sources.filter(isBusy)
  const idle = sources.filter((s) => !isBusy(s))
  const reindexable = idle.filter(canReindex)
  const facts = sources.reduce((n, s) => n + s.facts, 0)
  const addButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={() => setAdding(true)}>
      <LuPlus /> Add a source
    </Button>
  )

  return (
    <>
      <PageHeader title="Sources" subtitle="Import your career data. Everything stays on this computer." />
      <Box display="flex" gap="6" flexWrap="wrap" alignItems="flex-start">
        <Box flex="1 1 460px" minW="0">
          <Box display="flex" alignItems="center" gap="3" mb="3">
            <Heading as="h2" size="md" flex="1" color="app.text">
              Your sources
            </Heading>
            <Button
              size="sm"
              variant="outline"
              borderColor="app.borderStrong"
              color="app.text"
              disabled={reindexable.length === 0}
              onClick={() => reindex.mutate(reindexable.map((s) => s.source))}
            >
              <LuRefreshCw /> Reindex all
            </Button>
          </Box>
          {isError && (
            <Text role="alert" color="app.missText" fontSize="sm" mb="3">
              Could not load sources.
            </Text>
          )}
          {busy.length > 0 && <ProcessingCard sources={busy} />}
          {idle.map((s) => (
            <SourceCard
              key={s.source}
              source={s}
              onReindex={() => reindex.mutate([s.source])}
              onRemove={() => remove.mutate(s.source)}
            />
          ))}
          {sources.length === 0 && !isError && (
            <EmptyState title="No sources yet" description="Import a resume, LinkedIn export or text to get started.">
              {addButton}
            </EmptyState>
          )}
        </Box>
        <Box flex="1 1 360px" minW="0">
          {sources.length > 0 && addButton}
          {sources.length > 0 && (
            <Text role="status" color="app.muted" fontSize="sm" mt="4">
              {idle.length} {idle.length === 1 ? 'source' : 'sources'} indexed, {busy.length} processing. {facts} facts so
              far.
            </Text>
          )}
        </Box>
      </Box>
      <AddSourceDialog open={adding} onClose={() => setAdding(false)} />
    </>
  )
}
