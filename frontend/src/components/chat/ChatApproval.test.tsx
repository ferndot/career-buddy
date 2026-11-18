import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { queryClient } from '../../api'
import first from '../../test/fixtures/chat-interrupt.sse?raw'
import resumed from '../../test/fixtures/chat-interrupt-resumed.sse?raw'
import { renderApp } from '../../test/render'
import { ChatSidebar } from './ChatSidebar'

// The fixtures were encoded by the Python ag-ui SDK: a run that ends in a tool_call interrupt, and the run that resumes it.
const sse = (text: string) => new Response(text, { headers: { 'content-type': 'text/event-stream' } })

function propose() {
  const fetchMock = vi.fn((_url: string, _init: { body: string }) => Promise.resolve(sse(fetchMock.mock.calls.length === 1 ? first : resumed)))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<ChatSidebar open onClose={() => {}} />)
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), { target: { value: 'Make me Staff Engineer' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('approval card', () => {
  it('shows the exact change with Apply and Decline, and the composer waits', async () => {
    const fetchMock = propose()
    expect(await screen.findByText("Position 'Senior Engineer': title -> 'Staff Engineer'")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Decline' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledTimes(1)  // nothing is sent until the person answers
  })

  it('Apply resumes the run as approved, and the career queries are refetched', async () => {
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const fetchMock = propose()
    fireEvent.click(await screen.findByRole('button', { name: 'Apply' }))
    expect(await screen.findByText('Done.')).toBeInTheDocument()
    const body = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(body.resume).toEqual([{ interruptId: 'call1', status: 'resolved', payload: { approved: true } }])
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['facts'] }))
    for (const key of ['graph', 'duplicates', 'sources']) expect(invalidate).toHaveBeenCalledWith({ queryKey: [key] })
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
  })

  it('Decline resumes the run as not approved', async () => {
    const fetchMock = propose()
    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).resume).toEqual([{ interruptId: 'call1', status: 'resolved', payload: { approved: false } }])
  })
})
