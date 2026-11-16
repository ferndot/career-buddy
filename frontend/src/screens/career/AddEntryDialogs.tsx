import { Field, Input, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import { useAddEntry } from './api'
import { DateField } from './DateField'
import { FormDialog } from './FormDialog'

type Props = { open: boolean; onClose: () => void; personId: string }
type Change = { target: { value: string } }

function useEntryForm(initial: string[], onClose: () => void) {
  const [values, setValues] = useState(initial)
  const add = useAddEntry()
  const set = (i: number) => (e: Change) => setValues((v) => v.map((x, j) => (j === i ? e.target.value : x)))
  const setTo = (i: number) => (v: string) => setValues((cur) => cur.map((x, j) => (j === i ? v : x)))
  const done = () => {
    setValues(initial)
    add.reset()
    onClose()
  }
  return { values, set, setTo, add, done }
}

const field = (label: string, props: { value: string; onChange: (e: Change) => void; placeholder?: string }) => (
  <Field.Root mb="3">
    <Field.Label color="app.text2">{label}</Field.Label>
    <Input bg="app.surface" borderColor="app.borderStrong" {...props} />
  </Field.Root>
)

export function AddPositionDialog({ open, onClose, personId }: Props) {
  const {
    values: [title, org, started, finished, bullets],
    set,
    setTo,
    add,
    done,
  } = useEntryForm(['', '', '', '', ''], onClose)
  return (
    <FormDialog
      title="Add position"
      open={open}
      onClose={done}
      submit={{
        label: 'Add position',
        busy: add.isPending,
        disabled: !title.trim(),
        onSubmit: () =>
          add.mutate(
            {
              kind: 'Position',
              title,
              parent_id: personId,
              attributes: { organization: org, started, finished, description: bullets },
            },
            { onSuccess: done },
          ),
      }}
    >
      {field('Job title', { value: title, onChange: set(0) })}
      {field('Organization', { value: org, onChange: set(1) })}
      <DateField label="Start" value={started} onChange={setTo(2)} />
      <DateField label="End" value={finished} onChange={setTo(3)} allowPresent />
      <Field.Root>
        <Field.Label color="app.text2">Description</Field.Label>
        <Textarea rows={4} placeholder="What you did and what it achieved. Bullets or prose both work." bg="app.surface" borderColor="app.borderStrong" value={bullets} onChange={set(4)} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the position.</Field.ErrorText>}
    </FormDialog>
  )
}

export function AddEducationDialog({ open, onClose, personId }: Props) {
  const {
    values: [school, degree, started, finished],
    set,
    setTo,
    add,
    done,
  } = useEntryForm(['', '', '', ''], onClose)
  return (
    <FormDialog
      title="Add education"
      open={open}
      onClose={done}
      submit={{
        label: 'Add education',
        busy: add.isPending,
        disabled: !school.trim(),
        onSubmit: () =>
          add.mutate(
            // The importers title an entry by its degree, falling back to the school.
            { kind: 'Education', title: degree.trim() || school, parent_id: personId, attributes: { school, started, finished } },
            { onSuccess: done },
          ),
      }}
    >
      {field('School', { value: school, onChange: set(0) })}
      {field('Degree', { value: degree, onChange: set(1) })}
      <DateField label="Start" value={started} onChange={setTo(2)} />
      <DateField label="End" value={finished} onChange={setTo(3)} allowPresent />
      {add.isError && <Field.ErrorText>Could not add the education entry.</Field.ErrorText>}
    </FormDialog>
  )
}
