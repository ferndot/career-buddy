import { Box, Button, Flex, Text } from '@chakra-ui/react'
import type { ToolCallMessagePartProps } from '@assistant-ui/react'

const SHOWN = 140

/** What a tool returned, on one line. The tools answer in JSON or "Failed: ..."; the card keeps the start of it. */
function oneLine(result: unknown): string {
  const text = typeof result === 'string' ? result : JSON.stringify(result)
  return text.length > SHOWN ? `${text.slice(0, SHOWN)}...` : text
}

/**
 * The card for every tool call in the thread: the tool's name, what it was asked, and what it answered. A write tool waits for the person first:
 * the server ended the run with an interrupt, assistant-ui hands the call over with `approval`, and the prompt is the exact change in words.
 * Apply or Decline answers it with respondToApproval, which resumes the run; nothing is written before Apply.
 */
export function ToolCard({ toolName, argsText, result, approval, respondToApproval }: ToolCallMessagePartProps) {
  const asked = argsText && argsText !== '{}' ? argsText : ''
  const waiting = approval !== undefined && approval.approved === undefined && result === undefined
  return (
    <Box data-testid="tool-card" my="1.5" px="3" py="2" borderRadius="md" borderWidth="1px" borderColor="app.border" bg="app.surface2" fontSize="xs">
      <Text fontWeight="semibold" color="app.text">
        {toolName}
        {asked && !waiting && (
          <Text as="span" fontWeight="normal" color="app.muted">
            {' '}
            {asked}
          </Text>
        )}
      </Text>
      {waiting ? (
        <>
          <Text role="group" aria-label="Proposed change" color="app.text" mt="1" fontSize="sm" overflowWrap="anywhere">
            {approval.prompt ?? 'Make this change?'}
          </Text>
          <Flex gap="2" mt="2">
            <Button size="xs" bg="app.primary" color="app.onPrimary" onClick={() => respondToApproval({ approved: true })}>
              Apply
            </Button>
            <Button size="xs" variant="outline" onClick={() => respondToApproval({ approved: false })}>
              Decline
            </Button>
          </Flex>
        </>
      ) : (
        <Text color="app.text3" mt="0.5" overflowWrap="anywhere">
          {result === undefined ? 'Looking...' : oneLine(result)}
        </Text>
      )}
    </Box>
  )
}
