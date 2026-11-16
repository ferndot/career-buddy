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
  const { data: sources = [], isError, isPending } = useSources()
  const reindex = useReindexSources()
  const remove = useRemoveSource()
  const busy = sources.filter(isBusy)
  const idle = sources.filter((s) => !isBusy(s))
  const reindexable = idle.filter(canReindex)
  const addButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={() => setAdding(true)}>
      <LuPlus /> Add a source
    </Button>
  )

  return (
    <>
      <PageHeader title="Sources" subtitle="Import your career data. Everything stays on this computer." />
      <Box maxW="3xl">
        <Box display="flex" alignItems="center" gap="3" mb="3" flexWrap="wrap">
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
          {sources.length > 0 && addButton}
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
        {sources.length === 0 && !isError && !isPending && (
          <EmptyState title="No sources yet" description="Import a resume, LinkedIn export or text to get started.">
            {addButton}
          </EmptyState>
        )}
      </Box>
      <AddSourceDialog open={adding} onClose={() => setAdding(false)} />
    </>
  )
}
