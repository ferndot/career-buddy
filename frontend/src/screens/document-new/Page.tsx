import { Box } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import type { TemplateLayout } from '../documents/api'

export type Part = { title: string; node: ReactNode }

type Props = {
  layout: TemplateLayout // from the template: the header kind and which headings sit in the side column
  head: ReactNode // the name block
  parts: Part[] // the sections, in reading order
  label: string
  testId?: string
}

const INK = '#1a1a1a'

/** A white sheet laid out as the template says: its header (plain, centered or a band) and, when it has side headings, a side column. The colours are the layout's: accent for headings and the band, panel for the side column. */
export function Page({ layout, head, parts, label, testId }: Props) {
  const side = parts.filter((p) => layout.side.includes(p.title))
  const main = parts.filter((p) => !side.includes(p))
  const band = layout.header === 'band'
  const accent = layout.accent || INK
  const centered = layout.header === 'centered'
  const section = (p: Part, i: number) => (
    <Box key={i} display="flex" flexDirection="column" gap="1" mt="2">
      {p.title && <Box fontWeight="bold" fontSize="12px" letterSpacing="0.05em" color={accent} borderBottomWidth="1px" borderColor="#c8ccd4">{p.title}</Box>}
      {p.node}
    </Box>
  )
  return (
    <Box data-testid={testId} role="group" aria-label={label} bg="#ffffff" color={INK} borderWidth="1px" borderColor="#d5d9e0" borderRadius="md" boxShadow="sm" fontSize="13px" overflow="hidden" maxH="560px" overflowY="auto">
      <Box px="5" py="4" display="flex" flexDirection="column" gap="1" textAlign={centered ? 'center' : 'left'} alignItems={centered ? 'center' : 'stretch'} bg={band ? accent : '#ffffff'} color={band ? 'white' : INK} borderBottomWidth={layout.header === 'plain' && side.length ? '3px' : '0'} borderColor={accent}>
        {head}
      </Box>
      <Box px="5" pb="5" display="grid" gridTemplateColumns={side.length ? 'minmax(0, 1fr) minmax(0, 0.42fr)' : 'minmax(0, 1fr)'} gap="5">
        <Box>{main.map(section)}</Box>
        {side.length > 0 && <Box bg={layout.panel || undefined} px="3" pb="3" mt="2">{side.map(section)}</Box>}
      </Box>
    </Box>
  )
}
