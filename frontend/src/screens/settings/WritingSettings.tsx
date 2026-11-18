import { Box, Button, Flex, Text, Textarea } from '@chakra-ui/react'
import { useState } from 'react'
import { LuPlus, LuTrash2 } from 'react-icons/lu'
import { LoadingState } from '../../components'
import { ConfirmDialog } from '../career/ConfirmDialog'
import { errorMessage } from './llmApi'
import { MAX_LENGTH, MAX_RULES, useResetRules, useSaveRules, useSetStrictness, useStrictness, useWritingRules, type Kind, type KindRules, type Strictness } from './writingApi'

const KINDS = [['resume', 'Resume'], ['letter', 'Letter']] as const
const LEVELS: readonly [Strictness, string, string][] = [
  ['strict', 'Strict', 'Wording stays close to your facts.'],
  ['balanced', 'Balanced', 'Wording may be paraphrased and merged; numbers, titles, employers, dates, degrees and tools stay exact.'],
  ['loose', 'Loose', 'Wording may go further; still no new numbers, titles, employers, dates, degrees, schools or tools.'],
]

function StrictnessControl() {
  const level = useStrictness()
  const set = useSetStrictness()
  const current = set.data?.strictness ?? level.data?.strictness
  return (
    <Box as="fieldset" bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="4">
      <Text as="legend" fontWeight="semibold" color="app.text" mb="1">Strictness</Text>
      <Text color="app.muted" fontSize="sm" mb="3">How closely the wording follows your facts. Specifics are never loosened.</Text>
      {level.isError && <Text color="app.missText" role="alert">Could not load the strictness.</Text>}
      {set.isError && <Text color="app.missText" fontSize="sm" role="alert">{errorMessage(set.error)}</Text>}
      {current && LEVELS.map(([value, label, hint]) => (
        <Box as="label" key={value} display="block" mb="2">
          <input type="radio" name="strictness" value={value} checked={current === value} disabled={set.isPending}
            onChange={() => set.mutate(value)} style={{ marginRight: 8 }} />
          <Text as="span" color="app.text" fontWeight="medium">{label}</Text>
          <Text as="span" color="app.muted" fontSize="sm"> {hint}</Text>
        </Box>
      ))}
    </Box>
  )
}

export function WritingSettings() {
  const rules = useWritingRules()
  return (
    <>
      <Text color="app.text2" fontSize="sm" mb="4">
        General rules the writer follows for every resume and letter. The template's own instructions and the resume length
        still win over these rules, and nothing here lets the writer state a fact you have not given.
      </Text>
      <StrictnessControl />
      {rules.isPending && <LoadingState text="Loading the writing rules..." />}
      {rules.isError && <Text color="app.missText" role="alert">Could not load the writing rules.</Text>}
      {rules.data && KINDS.map(([kind, label]) => <KindEditor key={kind} kind={kind} label={label} saved={rules.data[kind]} />)}
    </>
  )
}

function KindEditor({ kind, label, saved }: { kind: Kind; label: string; saved: KindRules }) {
  const [draft, setDraft] = useState(saved.rules)
  const [confirming, setConfirming] = useState(false)
  const save = useSaveRules(kind)
  const reset = useResetRules(kind)
  const edit = (i: number, text: string) => setDraft(draft.map((r, j) => (j === i ? text : r)))
  const clean = draft.map((r) => r.trim()).filter(Boolean)
  const tooLong = draft.some((r) => r.trim().length > MAX_LENGTH)

  return (
    <Box as="section" aria-label={`${label} rules`} bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="4">
      <Text as="h2" fontWeight="semibold" color="app.text" mb="1">{label}</Text>
      <Text color="app.muted" fontSize="sm" mb="3">{saved.custom ? 'Using your own rules.' : 'Using the default rules.'}</Text>
      {draft.map((rule, i) => (
        <Flex key={i} gap="2" mb="2" align="flex-start">
          <Textarea aria-label={`${label} rule ${i + 1}`} value={rule} rows={2} autoresize
            onChange={(e) => edit(i, e.target.value)} />
          <Button variant="ghost" color="app.link" aria-label={`Remove ${label} rule ${i + 1}`}
            onClick={() => setDraft(draft.filter((_, j) => j !== i))}>
            <LuTrash2 />
          </Button>
        </Flex>
      ))}
      {tooLong && <Text color="app.missText" fontSize="sm" role="alert">A rule can be at most {MAX_LENGTH} characters.</Text>}
      {(save.isError || reset.isError) && <Text color="app.missText" fontSize="sm" role="alert">{errorMessage(save.error ?? reset.error)}</Text>}
      <Flex gap="2" mt="3" wrap="wrap">
        <Button size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" disabled={draft.length >= MAX_RULES}
          onClick={() => setDraft([...draft, ''])}>
          <LuPlus /> Add a rule
        </Button>
        <Button size="sm" bg="app.primary" color="app.onPrimary" loading={save.isPending} disabled={tooLong}
          onClick={() => save.mutate(clean, { onSuccess: () => setDraft(clean.length ? clean : saved.default) })}>
          Save {label.toLowerCase()} rules
        </Button>
        <Button size="sm" variant="ghost" color="app.link" onClick={() => setConfirming(true)}>Reset to defaults</Button>
      </Flex>
      <ConfirmDialog title={`Reset the ${label.toLowerCase()} rules?`} open={confirming} busy={reset.isPending} confirmLabel="Reset to defaults"
        onCancel={() => setConfirming(false)}
        onConfirm={() => reset.mutate(undefined, { onSuccess: () => { setDraft(saved.default); setConfirming(false) } })}>
        Your own {label.toLowerCase()} rules are replaced by the defaults.
      </ConfirmDialog>
    </Box>
  )
}
