import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '../../test/render'
import { SettingsScreen } from './SettingsScreen'

const defaults = { resume: ['Plain headings.', 'Strong verbs.'], letter: ['Three paragraphs.'] }
const initial = {
  resume: { rules: defaults.resume, default: defaults.resume, custom: false },
  letter: { rules: ['My own letter rule.'], default: defaults.letter, custom: true },
}

type Sent = { url: string; method?: string; body?: string }
const sent: Sent[] = []

function stub(failSave = false) {
  sent.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/writing/strictness')) {
      sent.push({ url: u, method: init?.method, body: init?.body as string | undefined })
      return new Response(JSON.stringify({ strictness: init?.method === 'PUT' ? JSON.parse(init.body as string).strictness : 'balanced', default: 'balanced' }))
    }
    if (u.includes('/api/writing/rules')) {
      sent.push({ url: u, method: init?.method, body: init?.body as string | undefined })
      if (init?.method === 'DELETE') return new Response(null, { status: 204 })
      if (init?.method === 'PUT') {
        return failSave
          ? new Response(JSON.stringify({ detail: 'nope' }), { status: 422 })
          : new Response(JSON.stringify({ rules: JSON.parse(init.body as string).rules, default: [], custom: true }))
      }
      return new Response(JSON.stringify(initial))
    }
    return new Response(JSON.stringify([]))
  }))
}

async function openWriting() {
  renderApp(<SettingsScreen />)
  fireEvent.click(screen.getByRole('tab', { name: 'Writing' }))
  return { resume: await screen.findByRole('region', { name: 'Resume rules' }), letter: await screen.findByRole('region', { name: 'Letter rules' }) }
}

afterEach(() => vi.unstubAllGlobals())

describe('Writing settings', () => {
  it('shows the defaults or the saved rules per kind, and says the template and length win', async () => {
    stub()
    const { resume, letter } = await openWriting()
    expect(within(resume).getByRole('textbox', { name: 'Resume rule 2' })).toHaveValue('Strong verbs.')
    expect(within(resume).getByText('Using the default rules.')).toBeInTheDocument()
    expect(within(letter).getByRole('textbox', { name: 'Letter rule 1' })).toHaveValue('My own letter rule.')
    expect(within(letter).getByText('Using your own rules.')).toBeInTheDocument()
    expect(screen.getByText(/template's own instructions and the resume length/)).toBeInTheDocument()
  })

  it('saves an edited, added and removed list as the override, without blank rules', async () => {
    stub()
    const { resume } = await openWriting()
    fireEvent.change(within(resume).getByRole('textbox', { name: 'Resume rule 1' }), { target: { value: ' Short headings. ' } })
    fireEvent.click(within(resume).getByRole('button', { name: 'Remove Resume rule 2' }))
    fireEvent.click(within(resume).getByRole('button', { name: 'Add a rule' }))
    fireEvent.click(within(resume).getByRole('button', { name: 'Add a rule' })) // a blank one, dropped on save
    fireEvent.change(within(resume).getAllByRole('textbox')[1], { target: { value: 'No jargon.' } })
    fireEvent.click(within(resume).getByRole('button', { name: 'Save resume rules' }))
    await waitFor(() => expect(sent.some((r) => r.method === 'PUT')).toBe(true))
    const put = sent.find((r) => r.method === 'PUT')!
    expect(put.url).toBe('/api/writing/rules/resume')
    expect(JSON.parse(put.body!)).toEqual({ rules: ['Short headings.', 'No jargon.'] })
  })

  it('offers three strictness levels, Balanced by default, and saves a change', async () => {
    stub()
    await openWriting()
    expect(await screen.findByRole('radio', { name: /^Balanced/ })).toBeChecked()
    expect(screen.getAllByRole('radio')).toHaveLength(3)
    fireEvent.click(screen.getByRole('radio', { name: /^Strict/ }))
    await waitFor(() => expect(screen.getByRole('radio', { name: /^Strict/ })).toBeChecked())
    const put = sent.find((r) => r.url === '/api/writing/strictness' && r.method === 'PUT')!
    expect(JSON.parse(put.body!)).toEqual({ strictness: 'strict' })
  })

  it('shows the server message when a save is refused', async () => {
    stub(true)
    const { resume } = await openWriting()
    fireEvent.click(within(resume).getByRole('button', { name: 'Save resume rules' }))
    expect(await screen.findByText('nope')).toBeInTheDocument()
  })

  it('resets to the defaults only after confirming', async () => {
    stub()
    const { letter } = await openWriting()
    fireEvent.click(within(letter).getByRole('button', { name: 'Reset to defaults' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Keep' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(sent.some((r) => r.method === 'DELETE')).toBe(false)
    fireEvent.click(within(letter).getByRole('button', { name: 'Reset to defaults' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reset to defaults' }))
    await waitFor(() => expect(sent.find((r) => r.method === 'DELETE')?.url).toBe('/api/writing/rules/letter'))
    await waitFor(() => expect(within(letter).getByRole('textbox', { name: 'Letter rule 1' })).toHaveValue('Three paragraphs.'))
  })
})
