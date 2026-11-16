import { Box, Text } from '@chakra-ui/react'
import type { ReactNode } from 'react'
import { RobotMascot } from '../brand'

type Props = {
  title: string
  description?: string
  /** Optional single primary action (a button). */
  children?: ReactNode
  /** A loading state: the thinking robot, announced politely to screen readers. */
  loading?: boolean
}

/** The one layout for "nothing here yet" and "loading": robot, title, short description, optional action. */
export function EmptyState({ title, description, children, loading }: Props) {
  return (
    <Box
      role={loading ? 'status' : undefined}
      textAlign="center"
      py="10"
      px="6"
      bg="app.surface"
      borderWidth="2px"
      borderStyle="dashed"
      borderColor="app.dash"
      borderRadius="lg"
    >
      <Box display="flex" justifyContent="center" mb="2">
        <RobotMascot mood={loading ? 'thinking' : 'happy'} size={72} />
      </Box>
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

export const LoadingState = ({ text }: { text: string }) => <EmptyState loading title={text} />
