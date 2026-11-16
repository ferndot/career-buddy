import { Box, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import { RobotMascot } from '../brand'

type Props = { title: string; description?: string; mascot?: boolean; children?: ReactNode }

export function EmptyState({ title, description, mascot, children }: Props) {
  return (
    <Box
      textAlign="center"
      py="10"
      px="6"
      bg="app.surface"
      borderWidth="2px"
      borderStyle="dashed"
      borderColor="app.dash"
      borderRadius="lg"
    >
      {mascot && (
        <Box display="flex" justifyContent="center" mb="2">
          <RobotMascot size={72} />
        </Box>
      )}
      <Text fontWeight="semibold" color="app.text">
        {title}
      </Text>
      {description && (
        <Text color="app.muted" fontSize="sm" mt="1">
          {description}
        </Text>
      )}
      {children && <Box mt="4">{children}</Box>}
    </Box>
  )
}
