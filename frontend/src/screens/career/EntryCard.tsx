import { Box, Flex, Heading, IconButton, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import { LuArrowDown, LuArrowUp, LuEye, LuEyeOff, LuPencil } from 'react-icons/lu'
import { useReorder, useReviseFact } from './api'
import type { Bullet, Entry } from './model'

/** One position or education entry; each bullet can be shown or hidden, moved up or down, and edited. */
export function EntryCard({ entry, children, onEditBullet }: { entry: Entry; children?: ReactNode; onEditBullet?: (b: Bullet) => void }) {
  const revise = useReviseFact()
  const reorder = useReorder()

  const toggle = (b: Bullet, shown: boolean) => {
    const { hidden: _drop, ...rest } = b.attributes
    revise.mutate({ id: b.id, attributes: shown ? rest : { ...rest, hidden: 'true' } })
  }
  const move = (from: number, to: number) => {
    const ids = entry.bullets.map((b) => b.id)
    ids.splice(to, 0, ...ids.splice(from, 1))
    reorder.mutate(ids.map((id, order) => ({ id, order })))
  }

  return (
    <Box bg="app.surface" borderWidth="1px" borderColor="app.border" borderRadius="lg" px="5" py="4" mb="4">
      <Heading as="h2" size="md" color="app.text">
        {entry.title}
      </Heading>
      <Text color="app.muted" fontSize="sm" mb={entry.bullets.length ? '2' : '0'}>
        {[entry.org, entry.dates].filter(Boolean).join(', ')}
      </Text>
      {entry.bullets.map((b, i) => (
        <Flex key={b.id} align="flex-start" gap="2" my="1.5">
          <Box flex="1" minW="0">
            <Text fontSize="sm" color={b.hidden ? 'app.muted' : 'app.text2'} textDecoration={b.hidden ? 'line-through' : undefined}>
              {b.title}
            </Text>
            <BulletDetails attributes={b.attributes} />
          </Box>
          <IconButton aria-label={`${b.hidden ? 'Show' : 'Hide'}: ${b.title}`} title={b.hidden ? 'Hidden from documents: show' : 'Shown on documents: hide'}
            size="2xs" variant="ghost" color={b.hidden ? 'app.muted' : 'app.text2'} onClick={() => toggle(b, !!b.hidden)}>
            {b.hidden ? <LuEyeOff /> : <LuEye />}
          </IconButton>
          {onEditBullet && (
            <IconButton aria-label={`Edit: ${b.title}`} size="2xs" variant="ghost" color="app.muted" onClick={() => onEditBullet(b)}>
              <LuPencil />
            </IconButton>
          )}
          <IconButton aria-label={`Move up: ${b.title}`} size="2xs" variant="ghost" color="app.muted" disabled={i === 0} onClick={() => move(i, i - 1)}>
            <LuArrowUp />
          </IconButton>
          <IconButton aria-label={`Move down: ${b.title}`} size="2xs" variant="ghost" color="app.muted" disabled={i === entry.bullets.length - 1} onClick={() => move(i, i + 1)}>
            <LuArrowDown />
          </IconButton>
        </Flex>
      ))}
      {children}
    </Box>
  )
}

/** The measured result of an achievement, under its text. */
function BulletDetails({ attributes: { result } }: { attributes: Record<string, string> }) {
  return result ? <Text pl="7" fontSize="xs" color="app.muted">{result}</Text> : null
}
