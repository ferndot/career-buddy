import { Button, Flex, Link as ChakraLink } from '@chakra-ui/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, PageHeader } from '../../components'
import { useFacts, useGraph } from './api'
import { CareerGraph } from './CareerGraph'
import { DuplicatesBanner } from './DuplicatesBanner'
import { CareerExplorer } from './CareerExplorer'
import { buildCareer } from './model'

export function CareerScreen() {
  const facts = useFacts()
  const graph = useGraph()
  const [view, setView] = useState<'explore' | 'map'>('explore')
  const career = useMemo(
    () => (facts.data && graph.data ? buildCareer(facts.data, graph.data.edges) : null),
    [facts.data, graph.data],
  )

  const header = (
    <PageHeader
      title="Career"
      subtitle="Browse your facts and their links. Untick a bullet to hide it from documents."
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

  return (
    <>
      {header}
      <DuplicatesBanner />
      <Flex gap="1" mb="4" wrap="wrap" align="center">
        {(['explore', 'map'] as const).map((v) => (
          <Button key={v} size="xs" aria-pressed={view === v} variant={view === v ? 'solid' : 'outline'}
            bg={view === v ? 'app.primary' : undefined} color={view === v ? 'app.onPrimary' : 'app.text2'}
            onClick={() => setView(v)}>
            {v === 'explore' ? 'Explore' : 'Map'}
          </Button>
        ))}
      </Flex>
      {view === 'explore' ? (
        <CareerExplorer facts={facts.data ?? []} edges={graph.data?.edges ?? []} career={career} />
      ) : (
        <CareerGraph facts={facts.data ?? []} edges={graph.data?.edges ?? []} />
      )}
    </>
  )
}
