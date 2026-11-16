import { Button, Flex, Link as ChakraLink } from '@chakra-ui/react'
import { type ReactNode, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, PageHeader } from '../../components'
import { useFacts, useGraph } from './api'
import { CareerBuddy } from './CareerBuddy'
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

  const header = (actions?: ReactNode) => (
    <PageHeader
      title="Career"
      subtitle="Browse your facts and how they connect. Use the eye icon to hide an item from documents."
      actions={actions}
    />
  )

  if (!career) {
    const loading = facts.isPending || graph.isPending
    return (
      <>
        {header()}
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

  const toggle = (
    <Flex gap="1" align="center">
      {(['explore', 'map'] as const).map((v) => (
        <Button key={v} size="xs" aria-pressed={view === v} variant={view === v ? 'solid' : 'outline'}
          bg={view === v ? 'app.primary' : undefined} color={view === v ? 'app.onPrimary' : 'app.text2'}
          onClick={() => setView(v)}>
          {v === 'explore' ? 'Explore' : 'Map'}
        </Button>
      ))}
    </Flex>
  )

  return (
    <>
      {header(toggle)}
      <DuplicatesBanner />
      {view === 'explore' ? (
        <CareerExplorer facts={facts.data ?? []} edges={graph.data?.edges ?? []} career={career} />
      ) : (
        <CareerBuddy facts={facts.data ?? []} edges={graph.data?.edges ?? []} />
      )}
    </>
  )
}
