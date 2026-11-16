import { Field, Input, NativeSelect } from '@chakra-ui/react'
import { useState } from 'react'
import { useAddEntry } from './api'
import { FormDialog } from './FormDialog'
import type { Fact } from './api'

type Change = { target: { value: string } }

export function AddSkillDialog({ open, onClose, personId }: { open: boolean; onClose: () => void; personId: string }) {
  const [name, setName] = useState('')
  const add = useAddEntry()
  const done = () => {
    setName('')
    add.reset()
    onClose()
  }
  return (
    <FormDialog
      title="Add skill"
      open={open}
      onClose={done}
      submit={{
        label: 'Add skill',
        busy: add.isPending,
        disabled: !name.trim(),
        onSubmit: () => add.mutate({ kind: 'Skill', title: name, parent_id: personId, attributes: {} }, { onSuccess: done }),
      }}
    >
      <Field.Root>
        <Field.Label color="app.text2">Skill</Field.Label>
        <Input bg="app.surface" borderColor="app.borderStrong" placeholder="TypeScript" value={name}
          onChange={(e: Change) => setName(e.target.value)} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the skill.</Field.ErrorText>}
    </FormDialog>
  )
}

/** An achievement belongs to a position, so the dialog asks which one. */
export function AddAchievementDialog({ open, onClose, positions }: { open: boolean; onClose: () => void; positions: Fact[] }) {
  const [positionId, setPositionId] = useState('')
  const [text, setText] = useState('')
  const add = useAddEntry()
  const chosen = positionId || positions[0]?.id || ''
  const done = () => {
    setPositionId('')
    setText('')
    add.reset()
    onClose()
  }
  return (
    <FormDialog
      title="Add achievement"
      open={open}
      onClose={done}
      submit={{
        label: 'Add achievement',
        busy: add.isPending,
        disabled: !text.trim() || !chosen,
        onSubmit: () =>
          add.mutate({ kind: 'Achievement', title: text, parent_id: chosen, attributes: {} }, { onSuccess: done }),
      }}
    >
      <Field.Root mb="3">
        <Field.Label color="app.text2">Position</Field.Label>
        <NativeSelect.Root>
          <NativeSelect.Field value={chosen} onChange={(e: Change) => setPositionId(e.target.value)} bg="app.surface" borderColor="app.borderStrong">
            {positions.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </NativeSelect.Field>
        </NativeSelect.Root>
      </Field.Root>
      <Field.Root>
        <Field.Label color="app.text2">Achievement</Field.Label>
        <Input bg="app.surface" borderColor="app.borderStrong" placeholder="Cut build times by 60%" value={text}
          onChange={(e: Change) => setText(e.target.value)} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the achievement.</Field.ErrorText>}
    </FormDialog>
  )
}
