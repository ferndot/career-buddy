import { Box, Button, Field, Input, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import { LuSparkles } from 'react-icons/lu'
import type { Preview, Profile } from '../documents/api'
import { Check } from './Check'
import { toggle, toggleMany, type Wizard } from './state'

type Props = {
  w: Wizard
  set: (patch: Partial<Wizard>) => void
  profile: Profile | undefined
  tailoring: Preview['tailoring'] | undefined
  loading: boolean
  failed: boolean
  onAddFact: () => void
}

const card = { bg: 'app.surface', borderWidth: '1px', borderColor: 'app.border', borderRadius: 'lg', p: '5' } as const
const h3 = { fontSize: 'sm', fontWeight: 'semibold', mb: '2', color: 'app.text' } as const

function Chip({ on, children }: { on: boolean; children: ReactNode }) {
  return (
    <Box
      display="inline-flex"
      alignItems="center"
      gap="2"
      fontSize="13px"
      px="3"
      py="1"
      mr="2"
      mb="2"
      borderRadius="full"
      borderWidth="1px"
      borderColor={on ? 'app.dash' : 'app.borderStrong'}
      bg={on ? 'app.activeBg' : 'app.surface'}
      color={on ? 'app.activeText' : 'app.text'}
    >
      {children}
    </Box>
  )
}

export function DetailsStep({ w, set, profile, tailoring, loading, failed, onAddFact }: Props) {
  if (!profile) {
    return <Text color="app.muted">{failed ? 'Could not load your profile.' : 'Loading your profile...'}</Text>
  }
  const missing = (tailoring?.missing ?? []).slice(0, 8)
  const matched = tailoring?.matched ?? []
  return (
    <Box display="flex" gap="6" flexWrap="wrap" alignItems="flex-start">
      <Box {...card} flex="1.4 1 420px" minW="0">
        <Box display="flex" alignItems="center" gap="3" flexWrap="wrap" bg="app.activeBg" borderRadius="md" px="3" py="2" mb="5">
          <Text as="span" display="inline-flex" alignItems="center" gap="1" fontSize="xs" fontWeight="medium" px="2" py="0.5" borderRadius="full" bg="app.infoTag" color="app.activeText">
            <LuSparkles /> Prefilled by AI
          </Text>
          <Text flex="1" fontSize="13px" color="app.activeText">
            {loading
              ? 'Reading the posting...'
              : w.jobText.trim()
                ? 'Filled from the job posting. Check before you continue.'
                : 'No posting given, so everything in your profile is selected.'}
          </Text>
        </Box>
        <Field.Root mb="5">
          <Field.Label color="app.text2">Headline</Field.Label>
          <Input value={w.headline} onChange={(e) => set({ headline: e.target.value })} bg="app.surface" borderColor="app.borderStrong" color="app.text" />
        </Field.Root>

        <Text {...h3}>Skills to include</Text>
        <Box mb="4" role="group" aria-label="Skills to include">
          {profile.skills.map((s, i) => {
            const id = profile.skill_ids[i]
            return (
              <Chip key={id} on={w.skillIds.includes(id)}>
                <Check label={s} checked={w.skillIds.includes(id)} onChange={(on) => set({ skillIds: toggle(w.skillIds, id, on) })} />
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
              <Check bold label={label} checked={ids.length > 0 && ids.every((i) => w.bullets.includes(i))} onChange={(on) => set({ bullets: toggleMany(w.bullets, ids, on) })} />
              {p.achievements.map((a, i) => (
                <Box key={ids[i]} pl="6">
                  <Check label={a} checked={w.bullets.includes(ids[i])} onChange={(on) => set({ bullets: toggle(w.bullets, ids[i], on) })} />
                </Box>
              ))}
            </Box>
          )
        })}

        <Text {...h3} mt="4">Education</Text>
        <Box display="flex" flexDirection="column" gap="2">
          {profile.education.map((e) => {
            const label = [e.degree, e.school].filter(Boolean).join(', ')
            return <Check key={e.id} label={label} checked={w.education.includes(e.id)} onChange={(on) => set({ education: toggle(w.education, e.id, on) })} />
          })}
        </Box>
      </Box>

      <Box {...card} bg="app.surface2" flex="1 1 260px" minW="0" as="aside">
        <Text {...h3}>Why these were chosen</Text>
        <Text fontSize="13px" color="app.text3" mb="4">
          {matched.length
            ? `The posting asks for ${matched.slice(0, 6).join(', ')}. These are covered by your profile.`
            : 'Without a posting there is nothing to match, so everything is kept.'}
        </Text>
        {missing.length > 0 && (
          <>
            <Text {...h3}>Missing from your profile</Text>
            <Text fontSize="13px" color="app.text3" mb="2">
              The posting mentions {missing.slice(0, 4).join(', ')}. Your facts do not. Only add what is true.
            </Text>
            <Button variant="ghost" color="app.link" pl="0" onClick={onAddFact}>Add a fact to your career</Button>
          </>
        )}
      </Box>
    </Box>
  )
}
