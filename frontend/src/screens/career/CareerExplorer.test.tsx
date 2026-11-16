import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { queryClient } from '../../api'
import { renderApp } from '../../test/render'
import { CareerExplorer } from './CareerExplorer'
import { buildCareer } from './model'

const f = (id: string, kind: string, title: string, attributes = {}) => ({ id, kind, title, attributes, source: 's' })
const facts = [
  f('p', 'Person', 'Jane Doe'),
  f('pos', 'Position', 'Senior Engineer'),
  f('org', 'Organization', 'Acme'),
  f('a1', 'Achievement', 'Cut build times by 60%'),
]
const edges = [
  { source: 'p', target: 'pos', kind: 'HAS_POSITION' },
  { source: 'pos', target: 'org', kind: 'AT' },
  { source: 'pos', target: 'a1', kind: 'ACHIEVED' },
]
const career = buildCareer(facts, edges)!

afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

it('switches kinds with tabs and follows a linked item to its detail', async () => {
  renderApp(<CareerExplorer facts={facts} edges={edges} career={career} />)
  expect(screen.getByRole('tab', { name: 'Organizations (1)' })).toBeInTheDocument()
  expect(screen.getByRole('checkbox', { name: 'Cut build times by 60%' })).toBeChecked() // first position's card

  // A real click focuses the tab first; Chakra tabs select on focus.
  const achievements = screen.getByRole('tab', { name: 'Achievements (1)' })
  fireEvent.focus(achievements)
  fireEvent.click(achievements)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Cut build times by 60%' })).toBeInTheDocument())

  fireEvent.click(screen.getByRole('button', { name: 'Senior Engineer' })) // linked position chip
  expect(screen.getByRole('tab', { name: 'Positions (1)' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Acme' })) // linked organization chip
  expect(screen.getByRole('heading', { name: 'Acme' })).toBeInTheDocument()
})

it('filters the list by the search text', () => {
  renderApp(<CareerExplorer facts={facts} edges={edges} career={career} />)
  fireEvent.change(screen.getByRole('textbox', { name: 'Search' }), { target: { value: 'zzz' } })
  expect(screen.getByText('Nothing here yet.')).toBeInTheDocument()
})
