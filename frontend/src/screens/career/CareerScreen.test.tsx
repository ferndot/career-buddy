import { fireEvent, screen } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { CareerScreen } from './CareerScreen'

const f = (id: string, kind: string, title: string, attributes = {}) => ({ id, kind, title, attributes, source: 's' })
const facts = [
  f('p', 'Person', 'Jane Doe'),
  f('pos', 'Position', 'Senior Engineer', { period: 'Mar 2019 - Present' }),
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
  '/api/duplicates': [{ kind: 'Organization', a: { id: 'o1', title: 'Acme' }, b: { id: 'o2', title: 'Acme Corp' }, score: 0.9 }],
}

afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear() // the app shares one client across renders
})

it('opens on the explorer with bullet checkboxes, the duplicates banner and add buttons', async () => {
  vi.stubGlobal('fetch', async (url: string) => new Response(JSON.stringify(routes[url]), { status: 200 }))
  renderApp(<CareerScreen />)
  expect((await screen.findAllByText('Senior Engineer')).length).toBeGreaterThanOrEqual(1) // list item and card
  expect(screen.getByRole('tab', { name: 'Positions (1)' })).toBeInTheDocument()
  expect(screen.getByText('Acme, Mar 2019 - Present')).toBeInTheDocument()
  expect(screen.getByRole('checkbox', { name: 'Cut build times by 60%' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Ran design reviews' })).not.toBeChecked()
  expect(await screen.findByText('1 possible duplicate')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Add position' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Add education' })).toBeInTheDocument()
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
