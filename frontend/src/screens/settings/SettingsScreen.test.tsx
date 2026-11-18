import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '../../test/render'
import { SettingsScreen } from './SettingsScreen'

const providers = [{ id: 'ollama', label: 'Ollama', base_url: 'http://localhost:11434/v1', url_editable: true, needs_key: false, off_device: false, hint: 'Start Ollama first.' }]
const listing = {
  active: 'a1',
  connections: [{ id: 'a1', preset: 'ollama', label: 'My Ollama', base_url: 'http://localhost:11434/v1', model: 'llama3', key_hint: null, read_only: false, off_device: false, destination: 'localhost' }],
}

afterEach(() => vi.unstubAllGlobals())

describe('SettingsScreen', () => {
  it('lists connections with active badge', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
      new Response(JSON.stringify(String(url).includes('providers') ? providers : listing))))
    renderApp(<SettingsScreen />)
    expect(await screen.findByText('My Ollama')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('llama3')).toBeInTheDocument() // the card shows the model only
    expect(screen.queryByText(/localhost:11434|Ollama ·/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Add a connection/ })).toBeInTheDocument()
  })

  it('has an Appearance tab where choosing dark sets the theme', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([]))))
    renderApp(<SettingsScreen />)
    fireEvent.click(screen.getByRole('tab', { name: 'Appearance' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Dark' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true'))
    expect(document.documentElement).toHaveClass('dark')
  })
})

describe('Editing a connection', () => {
  const sent: { url: string; method?: string; body?: string }[] = []
  const stub = (models: unknown) => vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    sent.push({ url: String(url), method: init?.method, body: init?.body as string | undefined })
    const u = String(url)
    if (u.includes('providers')) return new Response(JSON.stringify(providers))
    if (u.endsWith('/test')) return new Response(JSON.stringify(models))
    return new Response(JSON.stringify(init?.method === 'PATCH' ? listing.connections[0] : listing))
  }))
  const openEdit = async () => {
    renderApp(<SettingsScreen />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit My Ollama' }))
  }

  it('pre-fills the fields, filters the model list, and does not send a blank key', async () => {
    sent.length = 0
    stub({ ok: true, message: 'Connected.', models: ['llama3', 'llama3.1', 'mistral'] })
    await openEdit()
    expect(await screen.findByDisplayValue('My Ollama')).toBeInTheDocument()
    const model = await screen.findByRole('combobox', { name: 'Model' })
    expect(model).toHaveValue('llama3')
    expect(screen.getByPlaceholderText('Leave blank to keep the saved key')).toHaveValue('')
    fireEvent.focus(model)
    fireEvent.change(model, { target: { value: 'mis' } })
    const list = within(screen.getByRole('listbox'))
    expect(list.getAllByRole('option').map((o) => o.textContent)).toEqual(['mistral'])
    fireEvent.mouseDown(list.getByRole('option', { name: 'mistral' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true))
    const patch = sent.find((r) => r.method === 'PATCH')!
    expect(patch.url).toContain('/api/llm/connections/a1')
    expect(JSON.parse(patch.body!)).toEqual({ label: 'My Ollama', base_url: 'http://localhost:11434/v1', model: 'mistral' })
  })

  it('falls back to a plain text field, and says so, when the model list cannot be loaded', async () => {
    stub({ ok: false, message: 'Could not reach localhost.', models: [] })
    await openEdit()
    expect(await screen.findByText(/Could not load the model list/)).toBeInTheDocument()
    expect(screen.getByDisplayValue('llama3')).toBeInTheDocument()
  })
})
