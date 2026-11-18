import { AssistantRuntimeProvider, ComposerPrimitive, MessagePrimitive, ThreadPrimitive } from '@assistant-ui/react'
import { useAgUiInterrupts, useAgUiRuntime } from '@assistant-ui/react-ag-ui'
import { HttpAgent } from '@ag-ui/client'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { useMemo } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import first from '../../test/fixtures/chat-interrupt.sse?raw'
import resumed from '../../test/fixtures/chat-interrupt-resumed.sse?raw'
import { renderApp } from '../../test/render'
import { ToolCard } from './ToolCard'

// Phase 0 of the career-chat plan: an approval is assistant-ui's own interrupt. The fixtures were encoded by the Python ag-ui SDK.
// A run that ends with outcome "interrupt" must show the tool call as waiting for approval, and answering it must start the next run with `resume`.

function Open() {
  return <p>open interrupts: {useAgUiInterrupts().length}</p>
}

function Harness() {
  const runtime = useAgUiRuntime({ agent: useMemo(() => new HttpAgent({ url: '/api/chat' }), []) })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Open />
      <ThreadPrimitive.Messages
        components={{
          UserMessage: () => <MessagePrimitive.Parts />,
          AssistantMessage: () => <MessagePrimitive.Parts components={{ tools: { Fallback: ToolCard } }} />,
        }}
      />
      <ComposerPrimitive.Root>
        <ComposerPrimitive.Input aria-label="Message" />
        <ComposerPrimitive.Send>Send</ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </AssistantRuntimeProvider>
  )
}

const sse = (text: string) => new Response(text, { headers: { 'content-type': 'text/event-stream' } })
afterEach(() => vi.unstubAllGlobals())

describe('interrupts', () => {
  it('a run ending in an interrupt waits for approval, and the answer resumes the run', async () => {
    const fetchMock = vi.fn((_url: string, _init: { body: string }) => Promise.resolve(sse(fetchMock.mock.calls.length === 1 ? first : resumed)))
    vi.stubGlobal('fetch', fetchMock)
    renderApp(<Harness />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), { target: { value: 'Make me Staff Engineer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText("Position 'Senior Engineer': title -> 'Staff Engineer'")).toBeInTheDocument()
    expect(screen.getByText('open interrupts: 1')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(await screen.findByText('Done.')).toBeInTheDocument()
    expect(screen.getByText('open interrupts: 0')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const body = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(body.resume).toEqual([{ interruptId: 'call1', status: 'resolved', payload: { approved: true } }])  // a decline is resolved too, with approved: false
    expect(body.messages.map((m: { role: string }) => m.role)).toEqual(['user', 'assistant'])  // the open call has no tool message yet
    expect(body.messages[1].toolCalls[0]).toMatchObject({ id: 'call1', function: { name: 'edit_fact' } })
  })
})
