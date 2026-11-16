import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { renderApp } from '../test/render'
import { EmptyState, LoadingState } from './EmptyState'

it('renders the title, description, hidden mascot and optional action', () => {
  const { container } = renderApp(
    <EmptyState title="No things yet" description="Make one.">
      <button>Make a thing</button>
    </EmptyState>,
  )
  expect(screen.getByText('No things yet')).toBeInTheDocument()
  expect(screen.getByText('Make one.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Make a thing' })).toBeInTheDocument()
  const mascot = container.querySelector('[data-mascot]')
  expect(mascot).toHaveAttribute('aria-hidden', 'true')
  expect(mascot).toHaveAttribute('data-mascot', 'happy')
})

it('shows the thinking robot as a status while loading', () => {
  const { container } = renderApp(<LoadingState text="Loading things..." />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading things...')
  expect(container.querySelector('[data-mascot]')).toHaveAttribute('data-mascot', 'thinking')
})
