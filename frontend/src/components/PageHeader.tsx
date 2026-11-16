import { Box, Heading, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'

type Props = { title: string; subtitle?: string; actions?: ReactNode }

export function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <Box display="flex" alignItems="flex-start" gap="4" flexWrap="wrap" mb="6">
      <Box flex="1" minW="0">
        <Heading as="h1" size="2xl" fontWeight="semibold" color="app.text">
          {title}
        </Heading>
        {subtitle && (
          <Text color="app.muted" fontSize="sm" mt="1">
            {subtitle}
          </Text>
        )}
      </Box>
      {actions}
    </Box>
  )
}
