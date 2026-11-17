import { Box, Text, VisuallyHidden } from '@chakra-ui/react'
import { LuCheck } from 'react-icons/lu'
import type { Template } from '../documents/api'
import { kindLabel, missingInputs, type DocKind, type Wizard } from './state'

type Props = {
  w: Wizard
  templates: Template[]
  saved: DocKind[]
  onSelect: (k: DocKind) => void
}

/** One tab per document: a vertical list beside the step, a wrapping row on a phone. */
export function DocTabs({ w, templates, saved, onSelect }: Props) {
  return (
    <Box role="tablist" aria-label="Documents" aria-orientation="vertical" display="flex" flexDirection={{ base: 'row', md: 'column' }} flexWrap="wrap" gap="2" flex={{ md: '0 0 200px' }} minW="0" alignSelf="flex-start">
      {w.kinds.map((k) => {
        const d = w.docs[k]
        const on = k === w.active
        const done = [
          ['Template', !missingInputs(d, templates.find((t) => t.id === d.templateId))],
          ['Saved', saved.includes(k)],
        ] as const
        return (
          <Box key={k} as="button" role="tab" aria-selected={on} onClick={() => onSelect(k)} textAlign="left" px="3" py="2" borderRadius="md" borderWidth="2px" borderColor={on ? 'app.primary' : 'app.border'} bg={on ? 'app.activeBg' : 'app.surface'} color={on ? 'app.activeText' : 'app.text'} cursor="pointer" flex={{ base: '1 1 140px', md: 'none' }} minW="0">
            <Text fontWeight="semibold" fontSize="sm">{kindLabel(k)}</Text>
            <Box as="ul" listStyleType="none" fontSize="xs" color={on ? 'app.activeText' : 'app.muted'} m="0" p="0">
              {done.map(([label, ok]) => (
                <Box as="li" key={label} display="flex" alignItems="center" gap="1">
                  {ok ? <LuCheck aria-hidden="true" /> : <Box as="span" w="1em" />}
                  {label}
                  {ok && <VisuallyHidden> done</VisuallyHidden>}
                </Box>
              ))}
            </Box>
          </Box>
        )
      })}
    </Box>
  )
}
