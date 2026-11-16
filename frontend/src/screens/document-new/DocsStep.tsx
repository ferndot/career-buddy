import { Box, Text } from '@chakra-ui/react'
import { LuCheck } from 'react-icons/lu'
import { RobotMascot } from '../../brand'
import { DOC_KINDS, type DocKind, type Wizard } from './state'

type Props = { w: Wizard; set: (patch: Partial<Wizard>) => void }

export const DOCS_QUESTION = 'What kind of documents are you wanting to create?'

/** The robot asks from a bubble below it; the cards beneath are multi-select. */
export function DocsStep({ w, set }: Props) {
  const flip = (id: DocKind) => {
    const kinds = DOC_KINDS.map((k) => k.id).filter((k) => (k === id ? !w.kinds.includes(k) : w.kinds.includes(k)))
    set({ kinds, active: kinds.includes(w.active) ? w.active : (kinds[0] ?? 'resume') })
  }
  return (
    <Box maxW="560px" mx="auto" minH="50vh" display="flex" flexDirection="column" alignItems="center" justifyContent="center" gap="4">
      <RobotMascot />
      <Box
        position="relative"
        bg="app.surface"
        borderWidth="1px"
        borderColor="app.borderStrong"
        borderRadius="xl"
        px="5"
        py="3"
        textAlign="center"
        // the tail points up at the robot
        _before={{ content: '""', position: 'absolute', top: '-7px', left: 'calc(50% - 6px)', w: '12px', h: '12px', bg: 'app.surface', borderTopWidth: '1px', borderLeftWidth: '1px', borderColor: 'app.borderStrong', transform: 'rotate(45deg)' }}
      >
        <Text as="h1" fontSize="xl" fontWeight="semibold" color="app.text">{DOCS_QUESTION}</Text>
      </Box>
      <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap="3" w="full" role="group" aria-label="Documents">
        {DOC_KINDS.map((k) => {
          const on = w.kinds.includes(k.id)
          return (
            <Box
              key={k.id}
              as="button"
              role="checkbox"
              aria-checked={on}
              aria-label={k.label}
              onClick={() => flip(k.id)}
              textAlign="left"
              p="4"
              borderRadius="lg"
              borderWidth="2px"
              borderColor={on ? 'app.primary' : 'app.border'}
              bg={on ? 'app.activeBg' : 'app.surface'}
              color={on ? 'app.activeText' : 'app.text'}
              cursor="pointer"
              display="flex"
              alignItems="flex-start"
              gap="3"
            >
              <Box flex="1" minW="0">
                <Text fontWeight="semibold">{k.label}</Text>
                <Text fontSize="sm" color={on ? 'app.activeText' : 'app.muted'}>{k.hint}</Text>
              </Box>
              {on && <LuCheck aria-hidden="true" />}
            </Box>
          )
        })}
      </Box>
    </Box>
  )
}
