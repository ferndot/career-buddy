import { Field, Input, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import { useAddEntry } from './api'
import { FormDialog } from './FormDialog'

type Props = { open: boolean; onClose: () => void; personId: string }
type Change = { target: { value: string } }

function useEntryForm(initial: string[], onClose: () => void) {
  const [values, setValues] = useState(initial)
  const add = useAddEntry()
  const set = (i: number) => (e: Change) => setValues((v) => v.map((x, j) => (j === i ? e.target.value : x)))
  const done = () => {
    setValues(initial)
    add.reset()
    onClose()
  }
  return { values, set, add, done }
}

const field = (label: string, props: { value: string; onChange: (e: Change) => void; placeholder?: string }) => (
  <Field.Root mb="3">
    <Field.Label color="app.text2">{label}</Field.Label>
    <Input bg="app.surface" borderColor="app.borderStrong" {...props} />
  </Field.Root>
)

export function AddPositionDialog({ open, onClose, personId }: Props) {
  const {
    values: [title, org, when, bullets],
    set,
    add,
    done,
  } = useEntryForm(['', '', '', ''], onClose)
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
              attributes: { organization: org, period: when },
              bullets: bullets
                .split('\n')
                .map((b) => b.trim())
                .filter(Boolean),
            },
            { onSuccess: done },
          ),
      }}
    >
      {field('Job title', { value: title, onChange: set(0) })}
      {field('Organization', { value: org, onChange: set(1) })}
      {field('Dates', { value: when, onChange: set(2), placeholder: 'Mar 2019 - Present' })}
      <Field.Root>
        <Field.Label color="app.text2">Bullets (one per line)</Field.Label>
        <Textarea rows={4} bg="app.surface" borderColor="app.borderStrong" value={bullets} onChange={set(3)} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the position.</Field.ErrorText>}
    </FormDialog>
  )
}

export function AddEducationDialog({ open, onClose, personId }: Props) {
  const {
    values: [school, degree, when],
    set,
    add,
    done,
  } = useEntryForm(['', '', ''], onClose)
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
            { kind: 'Education', title: degree.trim() || school, parent_id: personId, attributes: { school, period: when } },
            { onSuccess: done },
          ),
      }}
    >
      {field('School', { value: school, onChange: set(0) })}
      {field('Degree', { value: degree, onChange: set(1) })}
      {field('Dates', { value: when, onChange: set(2), placeholder: '2012 - 2016' })}
      {add.isError && <Field.ErrorText>Could not add the education entry.</Field.ErrorText>}
    </FormDialog>
  )
}
