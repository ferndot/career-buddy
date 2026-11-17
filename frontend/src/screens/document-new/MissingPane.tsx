import { Box, Button, Text } from '@chakra-ui/react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddSkillDialog } from '../career/AddOtherDialogs'
import { useFacts } from '../career/api'
import type { Wizard } from './state'

/** What the model's review of the posting found that the facts lack. `unavailable`: there is no review (no model, or it did not answer). */
export type MissingReview = { missing: string[]; nice: string[]; unavailable: boolean }
type Props = { w: Wizard; review: MissingReview; set: (patch: Partial<Wizard>) => void }

const frame = { bg: 'app.surface2', borderWidth: '1px', borderColor: 'app.border', borderRadius: 'lg', p: '4', mb: '5' } as const

/**
 * One row per requirement the posting names that the career facts do not cover, must-haves first and nice-to-haves in a
 * collapsed group. Yes opens the skill form with the name filled in (the fact is created when the form is saved); No
 * records it as missing and moves on. Without a review there is nothing to ask, and no guessing from the text.
 */
export function MissingPane({ w, review, set }: Props) {
  const qc = useQueryClient()
  const person = useFacts().data?.find((f) => f.kind === 'Person')
  const [adding, setAdding] = useState<string | null>(null)
  const reply = (term: string, a: 'yes' | 'no') => set({ answers: { ...w.answers, [term]: a } })
  const open = review.missing.filter((t) => !w.answers[t])
  const openNice = review.nice.filter((t) => !w.answers[t])
  const none = [...review.missing, ...review.nice].filter((t) => w.answers[t] === 'no')
  if (review.unavailable) {
    return (
      <Box {...frame} role="status">
        <Text fontSize="sm" color="app.warnText">
          Connect a model in <Link to="/settings">Settings</Link> to check the job posting for requirements.
        </Text>
      </Box>
    )
  }
  if (!open.length && !openNice.length && !none.length && !adding) return null
  const row = (t: string) => (
    <Box key={t} display="flex" alignItems="center" gap="3" flexWrap="wrap" py="1">
      <Text flex="1 1 200px" minW="0" fontSize="sm" color="app.text">Do you have {t}?</Text>
      <Button size="xs" bg="app.primary" color="app.onPrimary" aria-label={`Yes, ${t}`} disabled={!person} onClick={() => setAdding(t)}>Yes</Button>
      <Button size="xs" variant="outline" color="app.text" borderColor="app.borderStrong" aria-label={`No, ${t}`} onClick={() => reply(t, 'no')}>No</Button>
    </Box>
  )
  return (
    <Box {...frame} role="group" aria-label="Requirements not in your career">
      {open.map(row)}
      {openNice.length > 0 && (
        <Box as="details" mt={open.length ? '2' : '0'}>
          <Text as="summary" fontSize="sm" color="app.muted" cursor="pointer">Nice to have ({openNice.length})</Text>
          {openNice.map(row)}
        </Box>
      )}
      {none.length > 0 && <Text fontSize="xs" color="app.muted" mt="2">Not in your career: {none.join(', ')}.</Text>}
      {adding && person && (
        <AddSkillDialog
          key={adding}
          open
          personId={person.id}
          initialName={adding}
          onClose={() => setAdding(null)}
          onAdded={() => {
            reply(adding, 'yes')
            void qc.invalidateQueries({ queryKey: ['profile'] }) // the new skill reaches the picker
          }}
        />
      )}
    </Box>
  )
}
