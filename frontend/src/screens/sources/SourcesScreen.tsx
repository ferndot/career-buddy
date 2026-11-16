import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react'
import { useEffect, useState } from 'react'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { EmptyState, PageHeader } from '../../components'
import { AddSourceDialog } from './AddSourceDialog'
import { ProcessingCard } from './ProcessingCard'
import { SourceCard } from './SourceCard'
import { SourceLogSidebar } from './SourceLogSidebar'
import { canReindex, isBusy, useReindexSources, useRemoveSource, useSources } from './sourcesApi'

export function SourcesScreen() {
  const [adding, setAdding] = useState(false)
  // Whose log is open: undefined = the user has not chosen (follow work as it starts), '' = closed on purpose.
  const [choice, setChoice] = useState<string | undefined>()
  const { data: sources = [], isError, isPending } = useSources()
  const reindex = useReindexSources()
  const remove = useRemoveSource()
  const busy = sources.filter(isBusy)
  const idle = sources.filter((s) => !isBusy(s))
  const reindexable = idle.filter(canReindex)
  const firstBusy = busy.find((s) => s.status === 'processing') ?? busy[0]
  useEffect(() => {
    if (choice === undefined && firstBusy) setChoice(firstBusy.source) // stays open after the work ends: the log is the summary
  }, [choice, firstBusy])
  const selected = sources.find((s) => s.source === choice)
  const addButton = (
    <Button bg="app.primary" color="app.onPrimary" onClick={() => setAdding(true)}>
      <LuPlus /> Add a source
    </Button>
  )

  return (
    <>
      <PageHeader title="Sources" subtitle="Import your career data. Everything stays on this computer." />
      <Flex direction={{ base: 'column', xl: 'row' }} gap="6" align={{ base: 'stretch', xl: 'flex-start' }}>
        <Box flex="1" minW="0" maxW="3xl">
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
          {busy.length > 0 && <ProcessingCard sources={busy} selected={choice ?? ''} onLog={setChoice} />}
          {idle.map((s) => (
            <SourceCard
              key={s.source}
              source={s}
              selected={choice === s.source}
              onLog={() => setChoice(s.source)}
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
        {selected && <SourceLogSidebar source={selected} onClose={() => setChoice('')} />}
      </Flex>
      <AddSourceDialog open={adding} onClose={() => setAdding(false)} />
    </>
  )
}
