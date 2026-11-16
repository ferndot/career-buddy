import { Box, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'

type Props = { title: string; description?: string; children?: ReactNode }

export function EmptyState({ title, description, children }: Props) {
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
