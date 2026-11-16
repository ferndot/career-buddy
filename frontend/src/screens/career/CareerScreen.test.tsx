import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { CareerScreen } from './CareerScreen'

const f = (id: string, kind: string, title: string, attributes = {}) => ({ id, kind, title, attributes, source: 's' })
const facts = [
  f('p', 'Person', 'Jane Doe'),
  f('pos', 'Position', 'Senior Engineer', { started: '2019-03', finished: 'present' }),
  f('org', 'Organization', 'Acme'),
  f('a1', 'Achievement', 'Cut build times by 60%'),
  f('a2', 'Achievement', 'Ran design reviews', { hidden: 'true' }),
]
const edges = [
  { source: 'p', target: 'pos', kind: 'HAS_POSITION' },
  { source: 'pos', target: 'org', kind: 'AT' },
  { source: 'pos', target: 'a1', kind: 'ACHIEVED' },
  { source: 'pos', target: 'a2', kind: 'ACHIEVED' },
]
const routes: Record<string, unknown> = {
  '/api/facts': facts,
  '/api/graph': { nodes: [], edges },
  '/api/duplicates': [{ kind: 'Organization', a: { id: 'o1', title: 'Acme' }, b: { id: 'o2', title: 'Acme Corp' }, score: 0.9, canonical_id: 'o2' }],
}

afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear() // the app shares one client across renders
})

it('opens on the explorer with bullet visibility toggles, the duplicates banner and add buttons', async () => {
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(routes[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  expect((await screen.findAllByText('Senior Engineer')).length).toBeGreaterThanOrEqual(1) // list item and card
  expect(screen.getByRole('tab', { name: 'Positions (1)' })).toBeInTheDocument()
  expect(screen.getByText('Acme, Mar 2019 – Present')).toBeInTheDocument() // the card
  expect(screen.getByText('Acme · Mar 2019 – Present')).toBeInTheDocument() // the list row names the employer
  expect(screen.getByRole('button', { name: 'Hide: Cut build times by 60%' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Show: Ran design reviews' })).toBeInTheDocument()
  expect(await screen.findByText('1 possible duplicate')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Add position' })).toBeInTheDocument() // on the Positions tab
})

it('switches to the map view', async () => {
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(routes[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Map' }))
  expect(screen.queryByRole('tab', { name: 'Positions (1)' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Map' })).toHaveAttribute('aria-pressed', 'true')
})

it('shows the empty state when there is no person yet', async () => {
  vi.stubGlobal('fetch', async (url: string) =>
    new Response(JSON.stringify(url === '/api/graph' ? { nodes: [], edges: [] } : []), { status: 200 }),
  )
  renderApp(<CareerScreen />)
  expect(await screen.findByText('Nothing to explore yet')).toBeInTheDocument()
})

it('edits an item title and keeps its other attributes', async () => {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => new Response(JSON.stringify(routes[url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit: Senior Engineer' }))
  const title = screen.getByLabelText('Title')
  fireEvent.change(title, { target: { value: 'Staff Engineer' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/facts/pos'), expect.objectContaining({ method: 'PATCH' })))
  const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/api/facts/pos'))
  const body = JSON.parse(String(call?.[1]?.body))
  expect(body.title).toBe('Staff Engineer')
  expect(body.attributes).toMatchObject({ started: '2019-03', finished: 'present' })
})

it('unlinks the organization of a position', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) =>
    init?.method === 'DELETE' ? new Response(null, { status: 204 }) : new Response(JSON.stringify(routes[url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Unlink Acme' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/links'), expect.objectContaining({ method: 'DELETE' })))
  const url = String(fetchMock.mock.calls.find(([, i]) => i?.method === 'DELETE')?.[0])
  expect(url).toContain('source_id=pos')
  expect(url).toContain('target_id=org')
  expect(url).toContain('kind=AT')
})

it('deletes an item only after confirmation', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) =>
    init?.method === 'DELETE' ? new Response(null, { status: 204 }) : new Response(JSON.stringify(routes[url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete: Senior Engineer' }))
  expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/api/facts/pos'), expect.objectContaining({ method: 'DELETE' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Confirm delete' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/facts/pos'), expect.objectContaining({ method: 'DELETE' })))
})

const withSkills = {
  ...routes,
  '/api/facts': [...facts, f('sk', 'Skill', 'TypeScript'), f('sk2', 'Skill', 'Python')],
  '/api/graph': { nodes: [], edges: [...edges, { source: 'pos', target: 'sk', kind: 'USES_SKILL' }] },
}
const skillFetch = () =>
  vi.fn(async (url: string, init?: RequestInit) =>
    init?.method === 'DELETE' ? new Response(null, { status: 204 })
      : init?.method === 'POST' && url === '/api/links' ? new Response('{}', { status: 201 })
      : new Response(JSON.stringify(withSkills[url as keyof typeof withSkills] ?? {}), { status: 200 }))

it('unlinks a skill from a position', async () => {
  const fetchMock = skillFetch()
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Unlink TypeScript' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/links'), expect.objectContaining({ method: 'DELETE' })))
  const url = String(fetchMock.mock.calls.find(([, i]) => i?.method === 'DELETE')?.[0])
  expect(url).toContain('source_id=pos')
  expect(url).toContain('target_id=sk')
  expect(url).toContain('kind=USES_SKILL')
})

it('links a skill picked in the add combobox', async () => {
  const fetchMock = skillFetch()
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  const input = await screen.findByRole('combobox', { name: 'Add skill' })
  input.focus()
  fireEvent.change(input, { target: { value: 'pyt' } })
  await waitFor(() => expect(input).toHaveAttribute('aria-expanded', 'true'))
  fireEvent.click(await screen.findByRole('option', { name: 'Python' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/links', expect.objectContaining({ method: 'POST' })))
  const call = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ source_id: 'pos', target_id: 'sk2', kind: 'USES_SKILL' })
})

it('shows the result of a bullet, not raw attribute keys', async () => {
  const withDetail: Record<string, unknown> = { ...routes, '/api/facts': facts.map((x) => (x.id === 'a1' ? { ...x, attributes: { result: 'cut build time 60%' } } : x)) }
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(withDetail[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  expect(await screen.findByText('cut build time 60%')).toBeInTheDocument()
  expect(screen.queryByText(/result/)).not.toBeInTheDocument()
})

it('lists skills under their category with level and years', async () => {
  const skills = [
    f('s1', 'Skill', 'Python', { category: 'Languages', level: 'Expert', years: '5' }),
    f('s2', 'Skill', 'Excel'),
  ]
  const r: Record<string, unknown> = { ...routes, '/api/facts': [...facts, ...skills] }
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(r[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Skills (2)' }))
  expect(await screen.findByText('Expert · 5 years')).toBeInTheDocument()
  expect(screen.getAllByText('Languages')[0]).toBeInTheDocument() // header (the detail card repeats the value)
  expect(screen.getByText('Uncategorized')).toBeInTheDocument()
})

it('saves the category, level and years of a new skill', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) =>
    init?.method === 'POST' ? new Response('{"id":"n"}', { status: 201 }) : new Response(JSON.stringify(routes[url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Skills (0)' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Add skill' }))
  fireEvent.change(await screen.findByPlaceholderText('TypeScript'), { target: { value: 'Rust' } })
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Languages' } })
  fireEvent.change(screen.getByLabelText('Level'), { target: { value: 'Advanced' } })
  fireEvent.change(screen.getByLabelText('Years'), { target: { value: '3' } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Add skill' }).at(-1)!)
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/facts', expect.objectContaining({ method: 'POST' })))
  const body = JSON.parse(String(fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')?.[1]?.body))
  expect(body).toMatchObject({ kind: 'Skill', title: 'Rust', attributes: { category: 'Languages', level: 'Advanced', years: '3' } })
})

it('links and unlinks skills on an achievement', async () => {
  const r: Record<string, unknown> = {
    ...withSkills,
    '/api/graph': { nodes: [], edges: [...edges, { source: 'a1', target: 'sk', kind: 'USES_SKILL' }] },
  }
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    init?.method === 'DELETE' ? new Response(null, { status: 204 })
      : init?.method === 'POST' ? new Response('{}', { status: 201 })
      : new Response(JSON.stringify(r[_url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Achievements (2)' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Unlink TypeScript' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/links'), expect.objectContaining({ method: 'DELETE' })))
  const url = String(fetchMock.mock.calls.find(([, i]) => i?.method === 'DELETE')?.[0])
  expect(url).toContain('source_id=a1')
  expect(url).toContain('target_id=sk')
  expect(url).toContain('kind=USES_SKILL')
  const input = await screen.findByRole('combobox', { name: 'Add skill' })
  input.focus()
  fireEvent.change(input, { target: { value: 'pyt' } })
  await waitFor(() => expect(input).toHaveAttribute('aria-expanded', 'true'))
  fireEvent.click(await screen.findByRole('option', { name: 'Python' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/links', expect.objectContaining({ method: 'POST' })))
  const call = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ source_id: 'a1', target_id: 'sk2', kind: 'USES_SKILL' })
})

it('names the employer on each position in the merge dropdown', async () => {
  const r: Record<string, unknown> = {
    ...routes,
    '/api/facts': [...facts, f('pos2', 'Position', 'Tech Lead', { started: '2015', finished: '2018' }), f('org2', 'Organization', 'Beta')],
    '/api/graph': { nodes: [], edges: [...edges, { source: 'p', target: 'pos2', kind: 'HAS_POSITION' }, { source: 'pos2', target: 'org2', kind: 'AT' }] },
  }
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(r[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit: Senior Engineer' }))
  expect(screen.getByRole('option', { name: 'Tech Lead - Beta' })).toBeInTheDocument()
})

it('merges a suggested duplicate into the fact the server says to keep', async () => {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => new Response(JSON.stringify(routes[url] ?? {}), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Review' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Merge' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/merges', expect.objectContaining({ method: 'POST' })))
  const call = fetchMock.mock.calls.find(([u]) => u === '/api/merges')
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ alias_id: 'o1', canonical_id: 'o2' })
})

const patchBody = (fetchMock: ReturnType<typeof vi.fn>) =>
  JSON.parse(String(fetchMock.mock.calls.find(([u, i]) => String(u).includes('/api/facts/pos') && i?.method === 'PATCH')?.[1]?.body))
const okFetch = (r: Record<string, unknown> = routes) =>
  vi.fn(async (url: string, init?: RequestInit) =>
    init?.method === 'POST' ? new Response('{"id":"n"}', { status: 201 }) : new Response(JSON.stringify(r[url] ?? {}), { status: 200 }))

it('edits the dates of a position in one field per bound, at whatever precision is typed', async () => {
  const fetchMock = okFetch()
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit: Senior Engineer' }))
  expect(screen.queryByLabelText('Dates')).not.toBeInTheDocument() // no free-text field
  expect(screen.queryByRole('combobox', { name: /precision/ })).not.toBeInTheDocument() // and no Year/Month/Day selector
  expect(screen.getByLabelText('Start')).toHaveValue('2019-03')
  expect(screen.getByLabelText('End')).toBeDisabled() // the end is Present
  expect(screen.getByLabelText('End: present')).toBeChecked()
  fireEvent.click(screen.getByLabelText('End: present'))
  fireEvent.change(screen.getByLabelText('End'), { target: { value: '2021-04-09' } })
  fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2019' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(patchBody(fetchMock).attributes).toMatchObject({ started: '2019', finished: '2021-04-09' }))
})

it('flags a date that is not one, keeps text that is not a date, and sends Present for an open end', async () => {
  const r = { ...routes, '/api/facts': facts.map((x) => (x.id === 'pos' ? { ...x, attributes: { period: 'Spring 2019' } } : x)) }
  const fetchMock = okFetch(r)
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit: Senior Engineer' }))
  expect(screen.getByLabelText('Dates as written')).toHaveValue('Spring 2019')
  fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2019-13' } })
  expect(screen.getByLabelText('Start')).toHaveAttribute('aria-invalid', 'true')
  fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2019-02-30' } })
  expect(screen.getByLabelText('Start')).toHaveAttribute('aria-invalid', 'true')
  fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2019-02' } })
  expect(screen.getByLabelText('Start')).toHaveAttribute('aria-invalid', 'false')
  fireEvent.click(screen.getByLabelText('End: present'))
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(patchBody(fetchMock).attributes).toMatchObject({ period: 'Spring 2019', started: '2019-02', finished: 'present' }))
})

it('adds a position with start and end dates', async () => {
  const fetchMock = okFetch()
  vi.stubGlobal('fetch', fetchMock)
  renderApp(<CareerScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Add position' }))
  fireEvent.change(await screen.findByLabelText('Job title'), { target: { value: 'Tech Lead' } })
  fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2021' } })
  fireEvent.click(screen.getByLabelText('End: present'))
  fireEvent.click(screen.getAllByRole('button', { name: 'Add position' }).at(-1)!)
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/facts', expect.objectContaining({ method: 'POST' })))
  const body = JSON.parse(String(fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')?.[1]?.body))
  expect(body).toMatchObject({ kind: 'Position', title: 'Tech Lead', attributes: { started: '2021', finished: 'present' } })
  expect(body.attributes.period).toBeUndefined()
})
