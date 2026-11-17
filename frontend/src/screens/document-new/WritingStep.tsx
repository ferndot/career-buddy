import { Box, Button, Text } from '@chakra-ui/react'
import { EmptyState } from '../../components'

type Props = { failed: boolean; reason: string; retry: () => void; back: () => void }

/** Shown between the template step and the last step while the model writes the text. Not a numbered step. A failure shows why. */
export function WritingStep({ failed, reason, retry, back }: Props) {
  return (
    <Box maxW="560px" mx="auto" minH="50vh" display="flex" flexDirection="column" justifyContent="center">
      {failed ? (
        <EmptyState title="Writing the documents" description="Could not write the text.">
          <Text fontSize="sm" color="app.missText" mb="3">{reason}</Text>
          <Box display="flex" gap="3" justifyContent="center" flexWrap="wrap" role="alert">
            <Button bg="app.primary" color="app.onPrimary" onClick={retry}>Try again</Button>
            <Button variant="outline" color="app.text" borderColor="app.borderStrong" onClick={back}>Back to templates</Button>
          </Box>
        </EmptyState>
      ) : (
        <EmptyState loading title="Writing the documents" description="Writing the text from your facts and the posting." />
      )}
    </Box>
  )
}
