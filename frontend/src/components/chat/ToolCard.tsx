import { Box, Text } from '@chakra-ui/react'
import type { ToolCallMessagePartProps } from '@assistant-ui/react'

const SHOWN = 140

/** What a tool returned, on one line. The tools answer in JSON or "Failed: ..."; the card keeps the start of it. */
function oneLine(result: unknown): string {
  const text = typeof result === 'string' ? result : JSON.stringify(result)
  return text.length > SHOWN ? `${text.slice(0, SHOWN)}...` : text
}

/** The card for every tool call in the thread: the tool's name, what it was asked, and what it answered. */
export function ToolCard({ toolName, argsText, result }: ToolCallMessagePartProps) {
  const asked = argsText && argsText !== '{}' ? argsText : ''
  return (
    <Box data-testid="tool-card" my="1.5" px="3" py="2" borderRadius="md" borderWidth="1px" borderColor="app.border" bg="app.surface2" fontSize="xs">
      <Text fontWeight="semibold" color="app.text">
        {toolName}
        {asked && (
          <Text as="span" fontWeight="normal" color="app.muted">
            {' '}
            {asked}
          </Text>
        )}
      </Text>
      <Text color="app.text3" mt="0.5" overflowWrap="anywhere">
        {result === undefined ? 'Looking...' : oneLine(result)}
      </Text>
    </Box>
  )
}
