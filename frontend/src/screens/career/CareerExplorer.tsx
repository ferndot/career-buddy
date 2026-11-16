import { Box, Button, Flex, Grid, Heading, IconButton, Input, Tabs, Text } from '@chakra-ui/react'
import { Fragment, type ReactNode, useMemo, useState } from 'react'
import { LuEye, LuEyeOff, LuPencil, LuTrash2 } from 'react-icons/lu'
import type { Edge, Fact } from './api'
import { useDeleteFact, useReviseFact } from './api'
import { AddEducationDialog, AddPositionDialog } from './AddEntryDialogs'
import { AddAchievementDialog, AddSkillDialog } from './AddOtherDialogs'
import { ConfirmDialog } from './ConfirmDialog'
import { EditFactDialog } from './EditFactDialog'
import { EntryCard } from './EntryCard'
import { AddLink, UnlinkButton, addRule, ruleFor, singleNoun } from './LinkControls'
import { isHidden } from './model'
import { type Explorer, type Kind, KIND_LABEL, KINDS, explore, groupPositions, groupSkills, subtitle } from './explore'
import type { Bullet, Career, Entry } from './model'

const HIDDEN_KEYS = ['order', 'hidden']

/** Browse the career by kind: pick a kind, pick an item, then follow its links to related items. */
export function CareerExplorer({ facts, edges, career }: { facts: Fact[]; edges: Edge[]; career: Career }) {
  const ex = useMemo(() => explore(facts, edges), [facts, edges])
  const [kind, setKind] = useState<Kind>('Position')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<string | null>(null)
  const [adding, setAdding] = useState<Kind | null>(null)
  const [editing, setEditing] = useState<Fact | null>(null)

  const items = ex.list(kind).filter((f) => f.title.toLowerCase().includes(query.trim().toLowerCase()))
  const groups = kind === 'Position' ? groupPositions(items, ex) : kind === 'Skill' ? groupSkills(items) : [{ org: '', years: '', items }]
  const current = (picked && ex.byId.get(picked)) || groups[0]?.items[0]
  const open = (f: Fact) => {
    setKind(f.kind as Kind)
    setPicked(f.id)
    setQuery('')
  }

  return (
    <>
    <Tabs.Root value={kind} variant="line" mb="4" lazyMount minW="0"
      onValueChange={(d) => { setKind(d.value as Kind); setPicked(null); setQuery('') }}>
      <Tabs.List aria-label="Kinds" flexWrap="nowrap" overflowX="auto" h="auto" css={{ scrollbarWidth: 'none' }}>
        {KINDS.map((k) => (
          <Tabs.Trigger key={k} value={k} flexShrink={0} whiteSpace="nowrap">
            {KIND_LABEL[k]} ({ex.list(k).length})
          </Tabs.Trigger>
        ))}
      </Tabs.List>
    </Tabs.Root>
    <Grid templateColumns={{ base: 'minmax(0, 1fr)', md: '340px minmax(0, 1fr)' }} gap={{ base: 4, md: 6 }} alignItems="start">
      <Box minW="0">
        <Flex gap="2" mb="3">
          <Input size="sm" flex="1" minW="0" placeholder={`Search ${KIND_LABEL[kind].toLowerCase()}`} aria-label="Search" value={query}
            onChange={(e) => setQuery(e.target.value)} bg="app.surface" borderColor="app.borderStrong" />
          <Button size="sm" variant="outline" flexShrink={0} onClick={() => setAdding(kind)}>{ADD_LABEL[kind]}</Button>
        </Flex>
        <Box maxH={{ base: '45vh', md: '70vh' }} overflowY="auto" pr="1">
          {groups.map((g) => (
            <Box key={g.org}>
              {g.org && (
                <Flex justify="space-between" gap="2" mt="3.5" mb="1" pl="3" fontSize="xs" color="app.muted" letterSpacing="wider">
                  <Text as="span" textTransform="uppercase">{g.org}</Text>
                  <Text as="span" flexShrink={0}>{g.years}</Text>
                </Flex>
              )}
              {g.items.map((f) => {
                const on = current?.id === f.id
                const line = subtitle(f, ex)
                return (
                  <Flex key={f.id} align="center" borderRadius="0 8px 8px 0" borderLeftWidth="2px"
                    borderLeftColor={on ? 'app.primary' : 'transparent'} bg={on ? 'app.surface' : undefined} _hover={{ bg: 'app.hover' }}>
                    <Button variant="ghost" justifyContent="flex-start" flex="1" minW="0" h="auto" py="2" px="3" whiteSpace="normal"
                      textAlign="left" aria-current={on || undefined} onClick={() => setPicked(f.id)}>
                      <Box>
                        <Text fontSize="sm" color={isHidden(f) ? 'app.muted' : on ? 'app.text' : 'app.text2'} fontWeight="medium">{f.title}</Text>
                        <Text fontSize="xs" color="app.muted">{[line, isHidden(f) ? 'hidden on documents' : ''].filter(Boolean).join(' · ')}</Text>
                      </Box>
                    </Button>
                    <RowActions fact={f} onEdit={() => setEditing(f)} onDeleted={() => { if (picked === f.id) setPicked(null) }} />
                  </Flex>
                )
              })}
            </Box>
          ))}
          {items.length === 0 && <Text color="app.muted" fontSize="sm">Nothing here yet.</Text>}
        </Box>
      </Box>
      <Box minW="0">
        {current ? <Detail fact={current} ex={ex} career={career} onOpen={open} /> : <Text color="app.muted">Pick an item.</Text>}
      </Box>
    </Grid>
    <EditFactDialog key={editing?.id} fact={editing} label={(c) => (c.kind === 'Position' ? withOrg(c, ex) : c.title)} candidates={editing ? ex.list(editing.kind as Kind).filter((c) => c.id !== editing.id) : []}
      onClose={() => setEditing(null)} />
    <AddPositionDialog open={adding === 'Position' || adding === 'Organization'} onClose={() => setAdding(null)} personId={career.personId} />
    <AddEducationDialog open={adding === 'Education'} onClose={() => setAdding(null)} personId={career.personId} />
    <AddSkillDialog open={adding === 'Skill'} onClose={() => setAdding(null)} personId={career.personId} />
    <AddAchievementDialog open={adding === 'Achievement'} onClose={() => setAdding(null)} positions={ex.list('Position')} />
    </>
  )
}

/** "Title - Employer" for a position, so same-titled roles can be told apart. */
const withOrg = (p: Fact, ex: Explorer) => [p.title, ex.neighbors(p.id).Organization?.[0]?.title].filter(Boolean).join(' - ')

/** Organizations have no entry of their own: an employer is named on a position, so that tab adds a position. */
const ADD_LABEL: Record<Kind, string> = {
  Position: 'Add position',
  Organization: 'Add position',
  Education: 'Add education',
  Achievement: 'Add achievement',
  Skill: 'Add skill',
}

function Detail({ fact, ex, career, onOpen }: { fact: Fact; ex: Explorer; career: Career; onOpen: (f: Fact) => void }) {
  const [editingBullet, setEditingBullet] = useState<Fact | null>(null)
  const entry = findEntry(career, fact.id)
  const links = <Links fact={fact} ex={ex} shown={new Set(entry?.bullets.map((b) => b.id))} onOpen={onOpen} />
  // A bullet is an achievement fact, so it is edited with the same dialog, merging among achievements.
  const editBullet = (b: Bullet) => setEditingBullet({ id: b.id, kind: 'Achievement', title: b.title, attributes: b.attributes, source: '' })
  return (
    <>
      {entry ? <EntryCard entry={entry} onEditBullet={editBullet}>{links}</EntryCard> : <Generic fact={fact}>{links}</Generic>}
      <EditFactDialog key={editingBullet?.id} fact={editingBullet}
        candidates={ex.list('Achievement').filter((c) => c.id !== editingBullet?.id)} onClose={() => setEditingBullet(null)} />
    </>
  )
}

/** Eye, edit and delete on each list row. Delete asks for confirmation in a popup, since it cannot be undone. */
function RowActions({ fact, onEdit, onDeleted }: { fact: Fact; onEdit: () => void; onDeleted: () => void }) {
  const revise = useReviseFact()
  const del = useDeleteFact()
  const [asking, setAsking] = useState(false)
  const shown = !isHidden(fact)
  const toggle = () => {
    const { hidden: _drop, ...rest } = fact.attributes
    revise.mutate({ id: fact.id, attributes: shown ? { ...rest, hidden: 'true' } : rest })
  }
  const kind = fact.kind.toLowerCase()
  return (
    <Flex gap="0" flexShrink={0} pr="1">
      <IconButton aria-label={shown ? `Hide from documents: ${fact.title}` : `Show on documents: ${fact.title}`}
        title={shown ? 'Shown on documents: hide' : 'Hidden from documents: show'} size="2xs" variant="ghost"
        color={shown ? 'app.text2' : 'app.muted'} onClick={toggle}>
        {shown ? <LuEye /> : <LuEyeOff />}
      </IconButton>
      <IconButton aria-label={`Edit: ${fact.title}`} title="Edit" size="2xs" variant="ghost" color="app.muted" onClick={onEdit}>
        <LuPencil />
      </IconButton>
      <IconButton aria-label={`Delete: ${fact.title}`} title="Delete" size="2xs" variant="ghost" color="app.missText" onClick={() => setAsking(true)}>
        <LuTrash2 />
      </IconButton>
      <ConfirmDialog
        title={`Delete this ${kind}?`}
        open={asking}
        busy={del.isPending}
        error={del.isError}
        confirmLabel="Confirm delete"
        onCancel={() => setAsking(false)}
        onConfirm={() => del.mutate(fact.id, { onSuccess: () => { setAsking(false); onDeleted() } })}
      >
        {fact.title}'s bullets are deleted too. This cannot be undone.
      </ConfirmDialog>
    </Flex>
  )
}

function findEntry(career: Career, id: string): Entry | undefined {
  return [...career.positions, ...career.education].find((e) => e.id === id)
}

/** Linked items grouped by kind, below a divider; each chip opens that item. Achievements already shown as bullets are skipped. */
function Links({ fact, ex, shown, onOpen }: { fact: Fact; ex: Explorer; shown: Set<string>; onOpen: (f: Fact) => void }) {
  const all = ex.edgesOf(fact.id).filter((l) => !shown.has(l.fact.id))
  const rows = KINDS.map((k) => [k, all.filter((l) => l.fact.kind === k).sort((a, b) => a.fact.title.localeCompare(b.fact.title))] as const)
    .filter(([k, list]) => list.length || (addRule(fact, k) && ex.list(k).length))
  if (!rows.length) return null
  return (
    <Grid templateColumns={{ base: 'minmax(0, 1fr)', md: 'max-content minmax(0, 1fr)' }} columnGap="3" rowGap="2" alignItems="baseline"
      borderTopWidth="1px" borderColor="app.border" mt="3.5" pt="3">
      {rows.map(([k, list]) => (
        <Fragment key={k}>
          <Text fontSize="xs" color="app.muted" textTransform="uppercase" letterSpacing="wider" whiteSpace="nowrap">
            {singleNoun(fact, k) ?? KIND_LABEL[k]}
          </Text>
          <Flex gap="1.5" wrap="wrap" mb={{ base: '2', md: '0' }}>
            {list.map((l) => (
              <Flex key={`${l.fact.id}:${l.kind}`} align="center">
                <Button size="xs" variant="outline" color="app.link" onClick={() => onOpen(l.fact)}>{l.fact.title}</Button>
                {ruleFor(fact, l.kind, l.isSource) && <UnlinkButton fact={fact} other={l.fact} edge={l.kind} isSource={l.isSource} />}
              </Flex>
            ))}
            {addRule(fact, k) && (
              <AddLink fact={fact} kind={k} current={list.map((l) => l.fact)}
                options={ex.list(k).filter((o) => !list.some((l) => l.fact.id === o.id))} />
            )}
          </Flex>
        </Fragment>
      ))}
    </Grid>
  )
}

function Generic({ fact, children }: { fact: Fact; children?: ReactNode }) {
  const details = Object.entries(fact.attributes).filter(([k, v]) => v && !HIDDEN_KEYS.includes(k))

  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="4">
      <Text fontSize="xs" color="app.muted" textTransform="uppercase" letterSpacing="wide">{fact.kind}</Text>
      <Heading as="h2" size="md" color="app.text" mb="2">{fact.title}</Heading>
      {details.map(([k, v]) => (
        <Text key={k} fontSize="sm" color="app.text2" mb="1"><Text as="span" color="app.muted">{k}: </Text>{v}</Text>
      ))}
      {children}
    </Box>
  )
}
