import { screen, within } from '@testing-library/react'
import { renderApp } from '../test/render'
import { ActivityLog, type ActivityEntry } from './ActivityLog'

const at = new Date(2026, 0, 1, 10, 0, 0).getTime()
const entries: ActivityEntry[] = [
  { at, level: 'info', text: 'Reading the posting' },
  { at: at + 1000, level: 'warn', text: 'No model connected' },
]

describe('ActivityLog', () => {
  it('shows the title, the status badge and the entries oldest first, with local times', () => {
    renderApp(<ActivityLog title="Job posting review" status="unavailable" entries={entries} actions={<button>Close</button>} />)
    expect(screen.getByRole('heading', { name: 'Job posting review' })).toBeInTheDocument()
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
    const rows = within(screen.getByRole('log')).getAllByText(/Reading the posting|No model connected/)
    expect(rows.map((r) => r.textContent)).toEqual([
      `${new Date(at).toLocaleTimeString([], { hour12: false })} Reading the posting`,
      `${new Date(at + 1000).toLocaleTimeString([], { hour12: false })} No model connected`,
    ])
    expect(rows[1]).toHaveAttribute('data-level', 'warn')
    expect(screen.queryByText('No activity yet')).not.toBeInTheDocument()
  })

  it('says so when there is nothing yet', () => {
    renderApp(<ActivityLog title="Document activity" status="idle" entries={[]} />)
    expect(screen.getByText('No activity yet')).toBeInTheDocument()
    expect(screen.getByText('Idle')).toBeInTheDocument()
  })
})
