import { Box, Field, Input, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import { LuSparkles } from 'react-icons/lu'
import type { Profile } from '../documents/api'
import { Check } from './Check'
import { toggle, toggleMany, type DocDraft } from './state'

type Props = {
  doc: DocDraft
  setDoc: (patch: Partial<DocDraft>) => void
  profile: Profile
  hasJob: boolean
  loading: boolean
}

const h3 = { fontSize: 'sm', fontWeight: 'semibold', mb: '2', color: 'app.text' } as const

function Chip({ on, children }: { on: boolean; children: ReactNode }) {
  return (
    <Box display="inline-flex" alignItems="center" gap="2" fontSize="13px" px="3" py="1" mr="2" mb="2" borderRadius="full" borderWidth="1px" borderColor={on ? 'app.dash' : 'app.borderStrong'} bg={on ? 'app.activeBg' : 'app.surface'} color={on ? 'app.activeText' : 'app.text'}>
      {children}
    </Box>
  )
}

/** Which career facts one document uses. */
export function FactsPicker({ doc, setDoc, profile, hasJob, loading }: Props) {
  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" p="5" minW="0">
      <Box display="flex" alignItems="center" gap="3" flexWrap="wrap" bg="app.activeBg" borderRadius="md" px="3" py="2" mb="5">
        <Text as="span" display="inline-flex" alignItems="center" gap="1" fontSize="xs" fontWeight="medium" px="2" py="0.5" borderRadius="full" bg="app.infoTag" color="app.activeText">
          <LuSparkles /> Prefilled by AI
        </Text>
        <Text flex="1" fontSize="13px" color="app.activeText">
          {loading ? 'Reading the posting...' : hasJob ? 'Filled from the job posting. Check before you continue.' : 'No posting given, so everything in your profile is selected.'}
        </Text>
      </Box>
      <Field.Root mb="5">
        <Field.Label color="app.text2">Headline</Field.Label>
        <Input value={doc.headline} onChange={(e) => setDoc({ headline: e.target.value })} bg="app.surface" borderColor="app.borderStrong" color="app.text" />
      </Field.Root>

      <Text {...h3}>Skills to include</Text>
      <Box mb="4" role="group" aria-label="Skills to include">
        {profile.skills.map((s, i) => {
          const id = profile.skill_ids[i]
          return (
            <Chip key={id} on={doc.skillIds.includes(id)}>
              <Check label={s} checked={doc.skillIds.includes(id)} onChange={(on) => setDoc({ skillIds: toggle(doc.skillIds, id, on) })} />
            </Chip>
          )
        })}
      </Box>

      <Text {...h3}>Experience</Text>
      {profile.positions.map((p) => {
        const label = `${p.title}${p.organization ? `, ${p.organization}` : ''}`
        const ids = p.achievement_ids
        return (
          <Box key={p.id} borderWidth="1px" borderColor="app.border" borderRadius="md" px="4" py="3" mb="3" display="flex" flexDirection="column" gap="2">
            <Check bold label={label} checked={ids.length > 0 && ids.every((i) => doc.bullets.includes(i))} onChange={(on) => setDoc({ bullets: toggleMany(doc.bullets, ids, on) })} />
            {p.achievements.map((a, i) => (
              <Box key={ids[i]} pl="6">
                <Check label={a} checked={doc.bullets.includes(ids[i])} onChange={(on) => setDoc({ bullets: toggle(doc.bullets, ids[i], on) })} />
              </Box>
            ))}
          </Box>
        )
      })}

      <Text {...h3} mt="4">Education</Text>
      <Box display="flex" flexDirection="column" gap="2">
        {profile.education.map((e) => {
          const label = [e.degree, e.school].filter(Boolean).join(', ')
          return <Check key={e.id} label={label} checked={doc.education.includes(e.id)} onChange={(on) => setDoc({ education: toggle(doc.education, e.id, on) })} />
        })}
      </Box>
    </Box>
  )
}
