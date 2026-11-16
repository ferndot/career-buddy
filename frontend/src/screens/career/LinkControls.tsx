import { Button, Combobox, Flex, Portal, Text, useFilter, useListCollection } from '@chakra-ui/react'
import { useEffect, useState } from 'react'
import { toaster } from '../../components/toaster'
import { type Fact, type LinkRef, useAddLink, useRemoveLink } from './api'
import type { Kind } from './explore'

/**
 * Links the UI can edit: edge kind, and the fact kinds at its source and target. `reverse` lets the target side add too
 * (a skill adds positions; an organization does not, a position moves from its own Employer row). An achievement adds
 * the positions it belongs to; a position still gets its bullets from its own card.
 */
const RULES = [
  { edge: 'AT', from: 'Position', to: 'Organization', reverse: false },
  { edge: 'ATTENDED', from: 'Education', to: 'Organization', reverse: false },
  { edge: 'USES_SKILL', from: 'Position', to: 'Skill', reverse: true },
  { edge: 'USES_SKILL', from: 'Achievement', to: 'Skill', reverse: false },
  { edge: 'ACHIEVED', from: 'Position', to: 'Achievement', reverse: true },
] as const

/** The rule behind an existing link of `fact`, seen from `fact`'s side. */
export const ruleFor = (fact: Fact, edge: string, isSource: boolean) =>
  RULES.find((r) => r.edge === edge && (isSource ? r.from === fact.kind : r.to === fact.kind))

/** The rule that lets `fact` add links to facts of `kind`, and whether `fact` is then the link's source. */
export function addRule(fact: Fact, kind: Kind) {
  const r = RULES.find((r) => (r.from === fact.kind && r.to === kind) || (r.reverse && r.to === fact.kind && r.from === kind))
  return r && { edge: r.edge, asSource: r.from === fact.kind }
}

/** "employer" / "school" when the group holds one organization at most, so it is changed rather than added to. */
export const singleNoun = (fact: Fact, kind: Kind) =>
  kind !== 'Organization' ? undefined : fact.kind === 'Position' ? 'employer' : fact.kind === 'Education' ? 'school' : undefined

const say = (title: string, type: 'info' | 'error' = 'info') => toaster.create({ title, type })

/** A small × on a chip's side that removes the link, then says so. */
export function UnlinkButton({ fact, other, edge, isSource }: { fact: Fact; other: Fact; edge: string; isSource: boolean }) {
  const remove = useRemoveLink()
  const [s, t] = isSource ? [fact.id, other.id] : [other.id, fact.id]
  const unlink = async () => {
    try {
      await remove.mutateAsync({ source_id: s, target_id: t, kind: edge })
      say(`Removed ${other.title}`)
    } catch {
      say(`Could not remove ${other.title}`, 'error')
    }
  }
  return (
    <Button size="xs" variant="ghost" px="1" minW="0" color="app.muted" aria-label={`Unlink ${other.title}`} disabled={remove.isPending}
      onClick={unlink}>×</Button>
  )
}

/** Type-to-filter picker: choosing an option calls `onPick` and leaves the field empty and open for the next one. */
function Picker({ label, options, onPick }: { label: string; options: Fact[]; onPick: (f: Fact) => void }) {
  const { contains } = useFilter({ sensitivity: 'base' })
  const { collection, filter, set } = useListCollection({
    initialItems: options, itemToString: (f) => f.title, itemToValue: (f) => f.id, filter: contains,
  })
  const ids = options.map((o) => o.id).join()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `ids` stands for `options`, whose identity changes every render
  useEffect(() => set(options), [ids])
  return (
    <Combobox.Root size="xs" w="44" collection={collection} value={[]} selectionBehavior="clear" openOnClick closeOnSelect={false}
      onInputValueChange={(e) => filter(e.inputValue)}
      onValueChange={(e) => { const f = options.find((o) => o.id === e.value[0]); if (f) onPick(f) }}>
      <Combobox.Control>
        <Combobox.Input aria-label={label} placeholder={label} />
      </Combobox.Control>
      <Portal>
        <Combobox.Positioner>
          <Combobox.Content>
            <Combobox.Empty>No match</Combobox.Empty>
            {collection.items.map((f) => (
              <Combobox.Item key={f.id} item={f}>
                <Combobox.ItemText>{f.title}</Combobox.ItemText>
              </Combobox.Item>
            ))}
          </Combobox.Content>
        </Combobox.Positioner>
      </Portal>
    </Combobox.Root>
  )
}

/**
 * Links `fact` to one more fact of `kind`; hidden when none is left. A group that holds one organization shows Change,
 * which links the new one first and only then removes the old, so a failure never leaves the fact without it.
 */
export function AddLink({ fact, kind, current, options }: { fact: Fact; kind: Kind; current: Fact[]; options: Fact[] }) {
  const add = useAddLink()
  const remove = useRemoveLink()
  const [changing, setChanging] = useState(false)
  const [error, setError] = useState('')
  const rule = addRule(fact, kind)!
  const noun = singleNoun(fact, kind)
  const ref = (id: string): LinkRef =>
    rule.asSource ? { source_id: fact.id, target_id: id, kind: rule.edge } : { source_id: id, target_id: fact.id, kind: rule.edge }

  const pick = async (f: Fact) => {
    setError('')
    try {
      await add.mutateAsync(ref(f.id))
    } catch {
      return setError(`Could not link ${f.title}.`)
    }
    for (const old of noun ? current : []) {
      try {
        await remove.mutateAsync(ref(old.id))
      } catch {
        return setError(`Linked ${f.title}, but could not remove ${old.title}. Both are linked for now.`)
      }
    }
    setChanging(false)
    say(noun ? `Moved to ${f.title}` : `Added ${f.title}`)
  }

  const label = noun ? `${current.length ? 'Change' : 'Set'} ${noun}` : `Add ${kind.toLowerCase()}`
  const control = !options.length ? null : noun && current.length && !changing && !error ? (
    <Button size="xs" variant="ghost" onClick={() => setChanging(true)}>Change</Button>
  ) : (
    <Picker label={label} options={options} onPick={pick} />
  )
  return (
    <Flex gap="2" align="center" wrap="wrap">
      {control}
      {error && <Text role="alert" fontSize="xs" color="app.missText">{error}</Text>}
    </Flex>
  )
}
