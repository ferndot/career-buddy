import { Box, Button, Text } from '@chakra-ui/react'
import { EmptyState } from '../../components'

type Props = { failed: boolean; reason: string; retry: () => void; skip: () => void }

/** Shown between steps 1 and 2 while the model reads the posting. Not a numbered step. A failure shows why, with a retry. */
export function ReviewStep({ failed, reason, retry, skip }: Props) {
  return (
    <Box maxW="560px" mx="auto" minH="50vh" display="flex" flexDirection="column" justifyContent="center">
      {failed ? (
        <EmptyState title="Fetching job description" description="Could not read the posting for requirements.">
          <Text fontSize="sm" color="app.missText" mb="3">{reason}</Text>
          <Box display="flex" gap="3" justifyContent="center" flexWrap="wrap" role="alert">
            <Button bg="app.primary" color="app.onPrimary" onClick={retry}>Try again</Button>
            <Button variant="outline" color="app.text" borderColor="app.borderStrong" onClick={skip}>Continue without requirements</Button>
          </Box>
        </EmptyState>
      ) : (
        <EmptyState loading title="Fetching job description" description="Reading the posting for requirements." />
      )}
    </Box>
  )
}
