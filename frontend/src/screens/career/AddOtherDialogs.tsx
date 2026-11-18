import { Field, Input, NativeSelect, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import { useAddEntry } from './api'
import { SKILL_CATEGORIES, SKILL_LEVELS } from './explore'
import { FormDialog } from './FormDialog'
import { OptionSelect } from './OptionSelect'
import { YearsInput } from './YearsInput'
import type { Fact } from './api'

type Change = { target: { value: string } }

const NO_SKILL = { category: '', years: '', level: '' }

type SkillProps = { open: boolean; onClose: () => void; personId: string; initialName?: string; onAdded?: () => void }

export function AddSkillDialog({ open, onClose, personId, initialName = '', onAdded }: SkillProps) {
  const [name, setName] = useState(initialName)
  const [attrs, setAttrs] = useState(NO_SKILL)
  const set = (k: keyof typeof NO_SKILL) => (v: string) => setAttrs({ ...attrs, [k]: v })
  const add = useAddEntry()
  const done = () => {
    setName(initialName)
    setAttrs(NO_SKILL)
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
        onSubmit: () => add.mutate({ kind: 'Skill', title: name, parent_id: personId, attributes: attrs }, { onSuccess: () => { onAdded?.(); done() } }),
      }}
    >
      <Field.Root mb="3">
        <Field.Label color="app.text2">Skill</Field.Label>
        <Input bg="app.surface" borderColor="app.borderStrong" placeholder="TypeScript" value={name}
          onChange={(e: Change) => setName(e.target.value)} />
      </Field.Root>
      <Field.Root mb="3">
        <Field.Label color="app.text2">Category</Field.Label>
        <OptionSelect value={attrs.category} onChange={set('category')} options={SKILL_CATEGORIES} empty="Uncategorized" />
      </Field.Root>
      <Field.Root mb="3">
        <Field.Label color="app.text2">Level</Field.Label>
        <OptionSelect value={attrs.level} onChange={set('level')} options={SKILL_LEVELS} empty="Not stated" />
      </Field.Root>
      <Field.Root>
        <Field.Label color="app.text2">Years</Field.Label>
        <YearsInput value={attrs.years} onChange={set('years')} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the skill.</Field.ErrorText>}
    </FormDialog>
  )
}

/** An achievement belongs to a position, so the dialog asks which one. */
export function AddAchievementDialog({ open, onClose, positions }: { open: boolean; onClose: () => void; positions: Fact[] }) {
  const [positionId, setPositionId] = useState('')
  const [text, setText] = useState('')
  const [result, setResult] = useState('')
  const add = useAddEntry()
  const chosen = positionId || positions[0]?.id || ''
  const done = () => {
    setPositionId('')
    setText('')
    setResult('')
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
          add.mutate({ kind: 'Achievement', title: text, parent_id: chosen, attributes: { result } }, { onSuccess: done }),
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
      <Field.Root mb="3">
        <Field.Label color="app.text2">Achievement</Field.Label>
        <Input bg="app.surface" borderColor="app.borderStrong" placeholder="Cut build times by 60%" value={text}
          onChange={(e: Change) => setText(e.target.value)} />
      </Field.Root>
      <Field.Root>
        <Field.Label color="app.text2">Result</Field.Label>
        <Textarea rows={2} bg="app.surface" borderColor="app.borderStrong" value={result}
          onChange={(e: Change) => setResult(e.target.value)} />
      </Field.Root>
      {add.isError && <Field.ErrorText>Could not add the achievement.</Field.ErrorText>}
    </FormDialog>
  )
}
