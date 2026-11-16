import { Box, Button, Text } from '@chakra-ui/react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { AddSkillDialog } from '../career/AddOtherDialogs'
import { useFacts } from '../career/api'
import type { Wizard } from './state'

type Props = { w: Wizard; missing: string[]; set: (patch: Partial<Wizard>) => void }

/**
 * One row per requirement the posting names that the career facts do not cover. Yes opens the skill form with the name
 * filled in (the fact is created when the form is saved); No records it as missing and moves on.
 */
export function MissingPane({ w, missing, set }: Props) {
  const qc = useQueryClient()
  const person = useFacts().data?.find((f) => f.kind === 'Person')
  const [adding, setAdding] = useState<string | null>(null)
  const reply = (term: string, a: 'yes' | 'no') => set({ answers: { ...w.answers, [term]: a } })
  const open = missing.filter((t) => !w.answers[t])
  const none = missing.filter((t) => w.answers[t] === 'no')
  if (!open.length && !none.length && !adding) return null
  return (
    <Box bg="app.surface2" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="4" mb="5" role="group" aria-label="Requirements not in your career">
      {open.map((t) => (
        <Box key={t} display="flex" alignItems="center" gap="3" flexWrap="wrap" py="1">
          <Text flex="1 1 200px" minW="0" fontSize="sm" color="app.text">Do you have {t}?</Text>
          <Button size="xs" bg="app.primary" color="app.onPrimary" aria-label={`Yes, ${t}`} disabled={!person} onClick={() => setAdding(t)}>Yes</Button>
          <Button size="xs" variant="outline" color="app.text" borderColor="app.borderStrong" aria-label={`No, ${t}`} onClick={() => reply(t, 'no')}>No</Button>
        </Box>
      ))}
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
