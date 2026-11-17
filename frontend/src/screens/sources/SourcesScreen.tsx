import { Box, Button, Heading, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { EmptyState, LoadingState, PageHeader, useActivityActions, useActivityPanel } from '../../components'
import { AddSourceDialog } from './AddSourceDialog'
import { ProcessingCard } from './ProcessingCard'
import { SourceCard } from './SourceCard'
import { sourceActivityId } from './SourceActivities'
import { isBusy, useReindexSources, useRemoveSource, useSources } from './sourcesApi'

export function SourcesScreen() {
  const [adding, setAdding] = useState(false)
  const { open, selected } = useActivityPanel()
  const { show } = useActivityActions()
  const { data: sources = [], isError, isPending } = useSources()
  const reindex = useReindexSources()
  const remove = useRemoveSource()
  const idle = sources.filter((s) => !isBusy(s))
  const chosen = open ? (sources.find((s) => sourceActivityId(s.source) === selected)?.source ?? '') : '' // whose stream the sidebar shows
  const addButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={() => setAdding(true)}>
      <LuPlus /> Add a source
    </Button>
  )

  return (
    <>
      <PageHeader title="Sources" />
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
            disabled={idle.length === 0}
            onClick={() => reindex.mutate(idle.map((s) => s.source))}
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
        {sources.map((s) =>
          isBusy(s) ? (
            <ProcessingCard key={s.source} sources={[s]} selected={chosen} onLog={(name) => show(sourceActivityId(name))} />
          ) : (
            <SourceCard
              key={s.source}
              source={s}
              selected={chosen === s.source}
              onLog={() => show(sourceActivityId(s.source))}
              onReindex={() => reindex.mutate([s.source])}
              onRemove={() => remove.mutate(s.source)}
            />
          ),
        )}
        {isPending && <LoadingState text="Loading your sources..." />}
        {sources.length === 0 && !isError && !isPending && (
          <EmptyState title="No sources yet" description="Import a resume or text to get started.">
            {addButton}
          </EmptyState>
        )}
      </Box>
      <AddSourceDialog open={adding} onClose={() => setAdding(false)} />
    </>
  )
}
