import { Box } from '@chakra-ui/react'
import type { ReactNode } from 'react'

/** A speech bubble the robot asks from; it sits directly below the robot with its tail pointing up at it. */
export function SpeechBubble({ children }: { children: ReactNode }) {
  return (
    <Box
      position="relative"
      bg="app.surface"
      borderWidth="1px"
      borderColor="app.borderStrong"
      borderRadius="xl"
      px="5"
      py="3"
      textAlign="center"
      _before={{ content: '""', position: 'absolute', top: '-7px', left: 'calc(50% - 6px)', w: '12px', h: '12px', bg: 'app.surface', borderTopWidth: '1px', borderLeftWidth: '1px', borderColor: 'app.borderStrong', transform: 'rotate(45deg)' }}
    >
      {children}
    </Box>
  )
}
