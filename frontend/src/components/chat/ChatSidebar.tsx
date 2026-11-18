import { Box, Button, Flex, IconButton, Link, Text, Textarea } from '@chakra-ui/react'
import { AssistantRuntimeProvider, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useAuiState } from '@assistant-ui/react'
import { useAgUiInterrupts, useAgUiRuntime } from '@assistant-ui/react-ag-ui'
import { HttpAgent } from '@ag-ui/client'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { LuMessageSquare, LuX } from 'react-icons/lu'
import { Link as RouterLink } from 'react-router-dom'
import { apiUrl } from '../../api/client'
import { endpoints } from '../../api/endpoints'
import { ResizeHandle } from '../ResizeHandle'
import { useResizableWidth } from '../useResizableWidth'
import { ToolCard } from './ToolCard'

/** The header button that shows or hides the chat. */
export function ChatButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <IconButton aria-label="Chat" aria-pressed={open} size="sm" variant="ghost" color="app.text3" _hover={{ bg: 'app.hover', color: 'app.text' }} onClick={onToggle}>
      <LuMessageSquare />
    </IconButton>
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root asChild>
      <Box alignSelf="flex-end" maxW="85%" px="3" py="2" borderRadius="lg" bg="app.activeBg" color="app.activeText" fontSize="sm" whiteSpace="pre-wrap">
        <MessagePrimitive.Parts />
      </Box>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root asChild>
      <Box alignSelf="flex-start" maxW="95%" fontSize="sm" color="app.text" whiteSpace="pre-wrap">
        <MessagePrimitive.Parts components={{ tools: { Fallback: ToolCard } }} />
      </Box>
    </MessagePrimitive.Root>
  )
}

/** The notice for a failed run. With no model connected the server says so, and the way out is Settings. */
function Notice({ message }: { message: string }) {
  return (
    <Box role="alert" mt="2" px="3" py="2" borderRadius="md" bg="app.surface2" borderWidth="1px" borderColor="app.border" fontSize="sm" color="app.missText">
      {message}{' '}
      {message.startsWith('Connect a model') && (
        <Link asChild color="app.link">
          <RouterLink to="/settings">Open Settings</RouterLink>
        </Link>
      )}
    </Box>
  )
}

function Thread({ error }: { error: string | null }) {
  const waiting = useAgUiInterrupts().length > 0 // a change is waiting for Apply or Decline; assistant-ui refuses a new message until it is answered
  return (
    <ThreadPrimitive.Root asChild>
      <Flex direction="column" flex="1" minH="0">
        <ThreadPrimitive.Viewport asChild>
          <Flex direction="column" flex="1" minH="0" overflowY="auto" gap="3" pb="2">
            <ThreadPrimitive.Empty>
              <Text fontSize="sm" color="app.muted">
                Ask about your career: your positions, achievements, skills or sources.
              </Text>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
            {error && <Notice message={error} />}
          </Flex>
        </ThreadPrimitive.Viewport>
        <ComposerPrimitive.Root asChild>
          <Flex gap="2" align="flex-end" pt="2">
            <ComposerPrimitive.Input asChild>
              <Textarea aria-label="Message" placeholder={waiting ? 'Apply or decline the change first' : 'Ask about your career'} disabled={waiting} rows={2} resize="none" fontSize="sm" />
            </ComposerPrimitive.Input>
            <ComposerPrimitive.Send asChild>
              <Button size="sm" bg="app.primary" color="app.onPrimary" disabled={waiting}>
                Send
              </Button>
            </ComposerPrimitive.Send>
          </Flex>
        </ComposerPrimitive.Root>
      </Flex>
    </ThreadPrimitive.Root>
  )
}

/** What the chat can change, so a finished run refetches it. Not every query: a document preview must not re-render. */
const CAREER_KEYS = [['facts'], ['graph'], ['duplicates'], ['sources']]

/**
 * A failed run is shown until the next run starts, and a finished run refetches the career queries, so an approved change shows on the career screen
 * (a run that only read costs a cheap local refetch). Inside the runtime provider, to read whether a run is going.
 */
function Chat({ error, clear }: { error: string | null; clear: () => void }) {
  const running = useAuiState((s) => s.thread.isRunning)
  const queries = useQueryClient()
  const was = useRef(false)
  useEffect(() => {
    if (running) clear()
    else if (was.current) CAREER_KEYS.forEach((queryKey) => void queries.invalidateQueries({ queryKey }))
    was.current = running
  }, [running, clear, queries])
  return <Thread error={error} />
}

/**
 * The career chat, beside the page. The thread lives in memory for the tab: closing the panel hides it, a reload clears it.
 * The server keeps no history; each message sends the whole thread.
 */
export function ChatSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const size = useResizableWidth('career-buddy.chatWidth')
  const agent = useMemo(() => new HttpAgent({ url: apiUrl(endpoints.chat()) }), [])
  const runtime = useAgUiRuntime({ agent, onError: (e) => setError(e.message) })
  const clear = useMemo(() => () => setError(null), [])
  return (
    <Box
      as="aside"
      aria-label="Chat"
      hidden={!open}
      display={open ? 'flex' : 'none'}
      flexDirection="column"
      p="4"
      bg="app.surface"
      borderColor="app.border"
      borderWidth="0 0 0 1px"
      flexShrink={0}
      minW="0"
      w="var(--chat-width)"
      position="sticky"
      top="0"
      h="100vh"
      style={{ '--chat-width': `${size.width}px` } as CSSProperties}
    >
      <ResizeHandle label="Resize chat" size={size} />
      <Flex align="center" mb="3">
        <Text flex="1" fontWeight="semibold" color="app.text">
          Chat
        </Text>
        <Button size="xs" variant="ghost" color="app.link" onClick={onClose} aria-label="Close chat">
          <LuX />
        </Button>
      </Flex>
      <AssistantRuntimeProvider runtime={runtime}>
        <Chat error={error} clear={clear} />
      </AssistantRuntimeProvider>
    </Box>
  )
}
