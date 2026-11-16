import { screen } from '@testing-library/react'
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
    expect(screen.getByRole('button', { name: /Add a connection/ })).toBeInTheDocument()
  })
})
