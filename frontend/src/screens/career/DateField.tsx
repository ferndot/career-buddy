import { Box, Flex, IconButton, Input, Popover, Text } from '@chakra-ui/react'
import { useState } from 'react'
import { LuCalendar } from 'react-icons/lu'
import { Calendar } from './Calendar'

const PARTIAL = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/

/** True for "2021", "2021-03" or "2021-03-14" naming a real year, month or day. Mirrors domain/dates.py. */
export function isPartialDate(text: string): boolean {
  const m = PARTIAL.exec(text)
  if (!m) return false
  const [y, mo, d] = [Number(m[1]), Number(m[2] ?? 1), Number(m[3] ?? 1)]
  return y > 0 && mo >= 1 && mo <= 12 && d >= 1 && d <= new Date(y, mo, 0).getDate()
}

/**
 * One date typed at whatever precision is known: "2021", "2021-03" or "2021-03-14". What is typed is what is stored, so
 * the length is the precision. With `allowPresent` a Present box marks an open end ("present"). Empty means not set; a
 * value that is not a date is flagged and the server refuses it.
 */
export function DateField({ label, value, onChange, allowPresent = false }: {
  label: string; value: string; onChange: (v: string) => void; allowPresent?: boolean
}) {
  const [text, setText] = useState(value === 'present' ? '' : value)
  const [present, setPresent] = useState(value === 'present')
  const [open, setOpen] = useState(false)
  const set = (t: string, p: boolean) => {
    setText(t)
    setPresent(p)
    onChange(p ? 'present' : t.trim())
  }

  return (
    <Box mb="3">
      <Text fontSize="sm" fontWeight="medium" color="app.text2" mb="1.5">{label}</Text>
      <Flex gap="3" align="center" wrap="wrap">
        <Input flex="1" minW="0" size="sm" bg="app.surface" borderColor="app.borderStrong" aria-label={label} disabled={present}
          placeholder="2021, 2021-03 or 2021-03-14" value={text} onChange={(e) => set(e.target.value, false)}
          aria-invalid={!present && !!text.trim() && !isPartialDate(text.trim())} />
        <Popover.Root open={open} onOpenChange={(d) => setOpen(d.open)} lazyMount unmountOnExit positioning={{ placement: 'bottom-end', strategy: 'fixed' }}>
          <Popover.Trigger asChild>
            <IconButton type="button" size="sm" variant="outline" borderColor="app.borderStrong" color="app.text" aria-label={`${label}: pick from calendar`} disabled={present}>
              <LuCalendar />
            </IconButton>
          </Popover.Trigger>
          <Popover.Positioner>
            <Popover.Content bg="app.surface" color="app.text" borderColor="app.borderStrong" w="auto" maxW="calc(100vw - 2rem)">
              <Popover.Body p="2"><Calendar value={text.trim()} onPick={(v) => { set(v, false); setOpen(false) }} /></Popover.Body>
            </Popover.Content>
          </Popover.Positioner>
        </Popover.Root>
        {allowPresent && (
          <Flex as="label" gap="1.5" align="center" cursor="pointer">
            <input type="checkbox" aria-label={`${label}: present`} checked={present} onChange={(e) => set(text, e.target.checked)} />
            <Text fontSize="sm" color="app.text2">Present</Text>
          </Flex>
        )}
      </Flex>
    </Box>
  )
}
