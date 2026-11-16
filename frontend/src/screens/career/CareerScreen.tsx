import { Box, Button, Flex, Link as ChakraLink } from '@chakra-ui/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, PageHeader } from '../../components'
import { useFacts, useGraph } from './api'
import { AddEducationDialog, AddPositionDialog } from './AddEntryDialogs'
import { CareerGraph } from './CareerGraph'
import { DuplicatesBanner } from './DuplicatesBanner'
import { EntryCard } from './EntryCard'
import { buildCareer } from './model'

export function CareerScreen() {
  const facts = useFacts()
  const graph = useGraph()
  const [adding, setAdding] = useState<'position' | 'education' | null>(null)
  const career = useMemo(
    () => (facts.data && graph.data ? buildCareer(facts.data, graph.data.edges) : null),
    [facts.data, graph.data],
  )

  const header = (
    <PageHeader
      title="Career"
      subtitle="Your facts as a graph. Tick the bullets you want to keep; untick to hide them."
      actions={
        <Button asChild bg="app.primary" color="app.onPrimary">
          <Link to="/documents/new">Continue to Generator</Link>
        </Button>
      }
    />
  )

  if (!career) {
    const loading = facts.isPending || graph.isPending
    return (
      <>
        {header}
        <EmptyState
          title={loading ? 'Loading your career…' : 'Nothing to explore yet'}
          description={loading ? undefined : 'Add a source to build your career graph.'}
        >
          {!loading && (
            <ChakraLink asChild color="app.link">
              <Link to="/sources">Go to Sources</Link>
            </ChakraLink>
          )}
        </EmptyState>
      </>
    )
  }

  const ghost = { variant: 'ghost' as const, color: 'app.link' }
  return (
    <>
      {header}
      <DuplicatesBanner />
      <Flex gap="6" wrap="wrap" align="flex-start">
        <Box flex="1 1 520px" minW="0">
          <CareerGraph career={career} />
        </Box>
        <Box flex="1 1 380px" minW="0">
          {[...career.positions, ...career.education].map((e) => (
            <EntryCard key={e.id} entry={e} />
          ))}
          <Button {...ghost} onClick={() => setAdding('position')}>
            Add position
          </Button>
          <Button {...ghost} onClick={() => setAdding('education')}>
            Add education
          </Button>
        </Box>
      </Flex>
      <AddPositionDialog open={adding === 'position'} onClose={() => setAdding(null)} personId={career.personId} />
      <AddEducationDialog open={adding === 'education'} onClose={() => setAdding(null)} personId={career.personId} />
    </>
  )
}
