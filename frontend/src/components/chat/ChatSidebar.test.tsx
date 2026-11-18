import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '../../test/render'
import read from '../../test/fixtures/chat-read.sse?raw'
import noModel from '../../test/fixtures/chat-no-model.sse?raw'
import { ChatSidebar } from './ChatSidebar'

// The fixtures are what POST /api/chat answered in tests/test_chat_api.py's scenarios: the contract between the two sides.
const stream = (sse: string) => () => Promise.resolve(new Response(sse, { headers: { 'content-type': 'text/event-stream' } }))

function ask(text: string) {
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

afterEach(() => vi.unstubAllGlobals())

describe('ChatSidebar', () => {
  it('shows the answer, and a card for the tool the answer used', async () => {
    vi.stubGlobal('fetch', vi.fn(stream(read)))
    renderApp(<ChatSidebar open onClose={() => {}} />)
    ask('What did I do with Kubernetes?')
    expect(await screen.findByText('You migrated 40 services to Kubernetes at Acme Corp.')).toBeInTheDocument()
    const card = screen.getByTestId('tool-card')
    expect(card).toHaveTextContent('find_facts')
    expect(card).toHaveTextContent('"total":2')
  })

  it('sends the tool call and its result back with the next message, because the server keeps nothing', async () => {
    const fetchMock = vi.fn((_url: string, _init: { body: string }) => stream(read)())
    vi.stubGlobal('fetch', fetchMock)
    renderApp(<ChatSidebar open onClose={() => {}} />)
    ask('What did I do with Kubernetes?')
    await screen.findByText(/You migrated 40 services/)
    ask('And Python?')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const { messages } = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(messages.map((m: { role: string }) => m.role)).toEqual(['user', 'assistant', 'tool', 'user'])
    expect(messages[1].toolCalls[0]).toMatchObject({ id: 'call1', function: { name: 'find_facts' } })
    expect(messages[2]).toMatchObject({ toolCallId: 'call1' })
  })

  it('tells the person to connect a model when the run fails for lack of one', async () => {
    vi.stubGlobal('fetch', vi.fn(stream(noModel)))
    renderApp(<ChatSidebar open onClose={() => {}} />)
    ask('hello')
    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent('Connect a model in Settings to chat about your career.')
    expect(screen.getByRole('link', { name: 'Open Settings' })).toHaveAttribute('href', '/settings')
  })
})
