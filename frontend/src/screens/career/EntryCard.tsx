import { Box, Checkbox, Flex, IconButton, Text } from '@chakra-ui/react'
import { LuArrowDown, LuArrowUp } from 'react-icons/lu'
import { useReorder, useReviseFact } from './api'
import type { Bullet, Entry } from './model'

/** One position or education entry; each bullet can be shown or hidden and moved up or down. */
export function EntryCard({ entry }: { entry: Entry }) {
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
      <Text fontWeight="semibold" fontSize="sm" color="app.text">
        {entry.title}
      </Text>
      <Text color="app.muted" fontSize="sm" mb={entry.bullets.length ? '2' : '0'}>
        {[entry.org, entry.dates].filter(Boolean).join(', ')}
      </Text>
      {entry.bullets.map((b, i) => (
        <Flex key={b.id} align="flex-start" gap="2" my="1.5">
          <Checkbox.Root
            flex="1"
            alignItems="flex-start"
            checked={!b.hidden}
            onCheckedChange={(d) => toggle(b, d.checked === true)}
            colorPalette="purple"
          >
            <Checkbox.HiddenInput />
            <Checkbox.Control mt="0.5" />
            <Checkbox.Label fontSize="sm" color={b.hidden ? 'app.muted' : 'app.text2'}>
              {b.title}
            </Checkbox.Label>
          </Checkbox.Root>
          <IconButton aria-label={`Move up: ${b.title}`} size="2xs" variant="ghost" color="app.muted" disabled={i === 0} onClick={() => move(i, i - 1)}>
            <LuArrowUp />
          </IconButton>
          <IconButton aria-label={`Move down: ${b.title}`} size="2xs" variant="ghost" color="app.muted" disabled={i === entry.bullets.length - 1} onClick={() => move(i, i + 1)}>
            <LuArrowDown />
          </IconButton>
        </Flex>
      ))}
    </Box>
  )
}
