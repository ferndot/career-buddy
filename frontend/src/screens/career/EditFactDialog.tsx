import { Button, Field, Flex, Input, NativeSelect, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import type { Fact } from './api'
import { useMerge, useReviseFact } from './api'
import { SKILL_CATEGORIES, SKILL_LEVELS } from './explore'
import { FormDialog } from './FormDialog'
import { OptionSelect } from './OptionSelect'

/** Attributes the screen manages itself: the hidden flag and display order are kept as they are. */
const KEEP = ['hidden', 'order']

/** Attributes a kind always offers, even when the fact has none yet. */
const OFFERED: Record<string, string[]> = { Achievement: ['result'], Skill: ['category', 'years', 'level'] }
const CHOICES: Record<string, { options: readonly string[]; empty: string }> = {
  category: { options: SKILL_CATEGORIES, empty: 'Uncategorized' },
  level: { options: SKILL_LEVELS, empty: 'Not stated' },
}
const label = (k: string) => k.charAt(0).toUpperCase() + k.slice(1)

/** Edits any item's title and its visible attributes, or merges it into another item of the same kind. Other attributes are sent back unchanged, since a revise replaces them all. */
export function EditFactDialog({ fact, candidates, onClose }: { fact: Fact | null; candidates: Fact[]; onClose: () => void }) {
  return fact ? <Form key={fact.id} fact={fact} candidates={candidates} onClose={onClose} /> : null
}

function Form({ fact, candidates, onClose }: { fact: Fact; candidates: Fact[]; onClose: () => void }) {
  const [target, setTarget] = useState('')
  const merge = useMerge()
  const present = Object.keys(fact.attributes).filter((k) => !KEEP.includes(k))
  const editable = [...present, ...(OFFERED[fact.kind] ?? []).filter((k) => !present.includes(k))]
  const [title, setTitle] = useState(fact.title)
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(editable.map((k) => [k, fact.attributes[k] ?? ''])),
  )
  const revise = useReviseFact()
  const save = () =>
    revise.mutate(
      { id: fact.id, title: title.trim(), attributes: { ...fact.attributes, ...values } },
      { onSuccess: onClose },
    )

  const kind = fact.kind.toLowerCase()

  return (
    <FormDialog
      title={`Edit ${kind}`}
      open
      onClose={onClose}
      submit={{ label: 'Save', busy: revise.isPending, disabled: !title.trim(), onSubmit: save }}
    >
      <Field.Root mb="3">
        <Field.Label color="app.text2">Title</Field.Label>
        <Input bg="app.surface" borderColor="app.borderStrong" value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field.Root>
      {editable.map((k) => (
        <Field.Root key={k} mb="3">
          <Field.Label color="app.text2">{label(k)}</Field.Label>
          {CHOICES[k] ? (
            <OptionSelect value={values[k]} onChange={(v) => setValues({ ...values, [k]: v })} {...CHOICES[k]} />
          ) : k === 'description' || k === 'result' ? (
            <Textarea rows={k === 'result' ? 2 : 4} bg="app.surface" borderColor="app.borderStrong" value={values[k]}
              onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
          ) : (
            <Input bg="app.surface" borderColor="app.borderStrong" value={values[k]}
              onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
          )}
        </Field.Root>
      ))}
      <Field.Root mb="3">
        <Field.Label color="app.text2">Merge into another {kind}</Field.Label>
        <Flex gap="2">
          <NativeSelect.Root size="sm" flex="1">
            <NativeSelect.Field aria-label="Merge target" value={target} onChange={(e) => setTarget(e.target.value)}
              bg="app.surface" borderColor="app.borderStrong">
              <option value="">Choose a {kind}</option>
              {candidates.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </NativeSelect.Field>
          </NativeSelect.Root>
          <Button size="sm" variant="outline" disabled={!target} loading={merge.isPending}
            onClick={() => merge.mutate({ alias_id: fact.id, canonical_id: target }, { onSuccess: onClose })}>
            Merge
          </Button>
        </Flex>
        <Field.HelperText color="app.muted">{fact.title} is hidden and shown as the chosen {kind}.</Field.HelperText>
        {merge.isError && <Field.ErrorText>Could not merge.</Field.ErrorText>}
      </Field.Root>
      {revise.isError && <Field.ErrorText>Could not save changes.</Field.ErrorText>}
    </FormDialog>
  )
}
