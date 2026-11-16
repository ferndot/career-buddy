import { Box, Button, Checkbox, Flex, Heading, Input, Text } from '@chakra-ui/react'
import { useMemo, useState } from 'react'
import type { Edge, Fact } from './api'
import { useReviseFact } from './api'
import { EntryCard } from './EntryCard'
import { type Explorer, type Kind, KIND_LABEL, KINDS, explore, subtitle } from './explore'
import type { Career, Entry } from './model'

const HIDDEN_KEYS = ['order', 'hidden']

/** Browse the career by kind: pick a kind, pick an item, then follow its links to related items. */
export function CareerExplorer({ facts, edges, career }: { facts: Fact[]; edges: Edge[]; career: Career }) {
  const ex = useMemo(() => explore(facts, edges), [facts, edges])
  const [kind, setKind] = useState<Kind>('Position')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<string | null>(null)

  const items = ex.list(kind).filter((f) => f.title.toLowerCase().includes(query.trim().toLowerCase()))
  const current = (picked && ex.byId.get(picked)) || items[0]
  const open = (f: Fact) => {
    setKind(f.kind as Kind)
    setPicked(f.id)
    setQuery('')
  }

  return (
    <Flex gap="4" align="flex-start" wrap="wrap">
      <Box flex="1 1 300px" minW="0">
        <Flex gap="1" wrap="wrap" mb="3" role="tablist" aria-label="Kinds">
          {KINDS.map((k) => (
            <Button key={k} size="xs" role="tab" aria-selected={k === kind} variant={k === kind ? 'solid' : 'outline'}
              bg={k === kind ? 'app.primary' : undefined} color={k === kind ? 'app.onPrimary' : 'app.text2'}
              onClick={() => { setKind(k); setPicked(null); setQuery('') }}>
              {KIND_LABEL[k]} ({ex.list(k).length})
            </Button>
          ))}
        </Flex>
        <Input size="sm" mb="2" placeholder={`Search ${KIND_LABEL[kind].toLowerCase()}`} aria-label="Search" value={query}
          onChange={(e) => setQuery(e.target.value)} bg="app.surface" borderColor="app.borderStrong" />
        <Box maxH="60vh" overflowY="auto" pr="1">
          {items.map((f) => (
            <Button key={f.id} variant={current?.id === f.id ? 'subtle' : 'ghost'} justifyContent="flex-start" w="100%"
              h="auto" py="2" mb="1" whiteSpace="normal" textAlign="left" onClick={() => setPicked(f.id)}>
              <Box>
                <Text fontSize="sm" color="app.text" fontWeight="medium">{f.title}</Text>
                <Text fontSize="xs" color="app.muted">{subtitle(f, ex)}</Text>
              </Box>
            </Button>
          ))}
          {items.length === 0 && <Text color="app.muted" fontSize="sm">Nothing here yet.</Text>}
        </Box>
      </Box>
      <Box flex="2 1 420px" minW="0">
        {current ? <Detail fact={current} ex={ex} career={career} onOpen={open} /> : <Text color="app.muted">Pick an item.</Text>}
      </Box>
    </Flex>
  )
}

function Detail({ fact, ex, career, onOpen }: { fact: Fact; ex: Explorer; career: Career; onOpen: (f: Fact) => void }) {
  const entry = findEntry(career, fact.id)
  return (
    <>
      {entry ? <EntryCard entry={entry} /> : <Generic fact={fact} />}
      <Links near={ex.neighbors(fact.id)} onOpen={onOpen} />
    </>
  )
}

function findEntry(career: Career, id: string): Entry | undefined {
  return [...career.positions, ...career.education].find((e) => e.id === id)
}

/** Linked items grouped by kind; each chip opens that item. */
function Links({ near, onOpen }: { near: ReturnType<Explorer['neighbors']>; onOpen: (f: Fact) => void }) {
  return (
    <>
      {KINDS.map((k) =>
        near[k]?.length ? (
          <Box key={k} mb="3">
            <Text fontSize="xs" color="app.muted" textTransform="uppercase" mb="1">{`Linked ${KIND_LABEL[k].toLowerCase()}`}</Text>
            <Flex gap="1" wrap="wrap">
              {near[k]?.map((f) => (
                <Button key={f.id} size="xs" variant="outline" color="app.link" onClick={() => onOpen(f)}>{f.title}</Button>
              ))}
            </Flex>
          </Box>
        ) : null,
      )}
    </>
  )
}

function Generic({ fact }: { fact: Fact }) {
  const revise = useReviseFact()
  const shown = fact.attributes.hidden !== 'true'
  const toggle = (on: boolean) => {
    const { hidden: _drop, ...rest } = fact.attributes
    revise.mutate({ id: fact.id, attributes: on ? rest : { ...rest, hidden: 'true' } })
  }
  const details = Object.entries(fact.attributes).filter(([k, v]) => v && !HIDDEN_KEYS.includes(k))

  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="4">
      <Text fontSize="xs" color="app.muted" textTransform="uppercase" letterSpacing="wide">{fact.kind}</Text>
      <Heading as="h2" size="md" color="app.text" mb="2">{fact.title}</Heading>
      <Checkbox.Root checked={shown} onCheckedChange={(d) => toggle(d.checked === true)} colorPalette="purple" mb="3">
        <Checkbox.HiddenInput />
        <Checkbox.Control />
        <Checkbox.Label fontSize="sm" color="app.text2">Shown on documents</Checkbox.Label>
      </Checkbox.Root>
      {details.map(([k, v]) => (
        <Text key={k} fontSize="sm" color="app.text2" mb="1"><Text as="span" color="app.muted">{k}: </Text>{v}</Text>
      ))}
    </Box>
  )
}
