import { fireEvent, screen, within } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from '../app/AppShell'
import { openLogs, renderApp, renderShell } from '../test/render'
import { useActivityLog } from './activityStore'
import { useState } from 'react'

// A page that starts agent work through the store's public hook, as the wizard does.
function Page() {
  const newLog = useActivityLog()
  const [review] = useState(() => newLog('Job posting review')) // one activity for this page
  const [writing] = useState(() => newLog('Document: Resume'))
  return (
    <>
      <button onClick={() => review('info', 'Reading the posting', 'working')}>Start review</button>
      <button onClick={() => review('info', 'Found 3 must-have requirements', 'done')}>Finish review</button>
      <button onClick={() => writing('error', 'Failed: The writer is busy.', 'failed')}>Fail writing</button>
    </>
  )
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }))
const sidebar = () => screen.getByRole('complementary', { name: 'Activity' })

describe('the activity sidebar', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn(async () => new Response('[]'))))
  afterEach(() => vi.unstubAllGlobals())

  it('is closed until the Logs button next to Settings opens it, and the button or X closes it', () => {
    renderShell(<Page />)
    expect(screen.queryByRole('complementary', { name: 'Activity' })).not.toBeInTheDocument()
    const settings = screen.getByRole('link', { name: 'Settings' })
    expect(settings.parentElement).toContainElement(screen.getByRole('button', { name: 'Logs' }))
    click('Logs')
    expect(sidebar()).toBeInTheDocument()
    click('Logs')
    expect(screen.queryByRole('complementary', { name: 'Activity' })).not.toBeInTheDocument()
    click('Logs')
    click('Close log')
    expect(screen.queryByRole('complementary', { name: 'Activity' })).not.toBeInTheDocument()
  })

  it('takes its place in the page layout beside the content instead of covering it', () => {
    renderShell(<Page />)
    openLogs()
    expect(sidebar().parentElement).toContainElement(screen.getByRole('main')) // same row as the page
    expect(getComputedStyle(sidebar()).position).not.toBe('fixed')
  })

  it('lists one entry per activity, with its status and the time of its last line', () => {
    renderShell(<Page />)
    openLogs()
    expect(within(sidebar()).getByText('No activity yet')).toBeInTheDocument()
    click('Start review')
    click('Fail writing')
    click('Finish review')
    const items = within(within(sidebar()).getByRole('list', { name: 'Activities' })).getAllByRole('listitem')
    expect(items).toHaveLength(2) // two lines of the review make one entry
    expect(items[0]).toHaveTextContent(/Job posting review/)
    expect(items[0]).toHaveTextContent('Done')
    expect(items[0]).toHaveTextContent(/\d\d:\d\d:\d\d/)
    expect(items[1]).toHaveTextContent(/Document: Resume.*Failed/)
  })

  it('shows the lines of the clicked activity, and Back returns to the list', () => {
    renderShell(<Page />)
    click('Start review')
    click('Finish review')
    click('Fail writing')
    openLogs(/Job posting review/)
    const lines = within(screen.getByRole('log')).getAllByText(/Reading|Found/).map((e) => e.textContent!.replace(/^\S+ /, ''))
    expect(lines).toEqual(['Reading the posting', 'Found 3 must-have requirements']) // newest last
    expect(screen.queryByText(/The writer is busy/)).not.toBeInTheDocument() // another activity's line
    click('Back to all activities')
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
    fireEvent.click(within(sidebar()).getByRole('button', { name: /Document: Resume/ }))
    expect(within(screen.getByRole('log')).getByText(/Failed: The writer is busy\./)).toHaveAttribute('data-level', 'error')
  })

  it('keeps the activities, and the open sidebar, when the page changes', () => {
    renderApp(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/sources" element={<Page />} />
          <Route path="/career" element={<p>Career page</p>} />
        </Route>
      </Routes>,
      '/sources',
    )
    click('Start review')
    openLogs()
    fireEvent.click(screen.getByRole('link', { name: 'Career' }))
    expect(screen.getByText('Career page')).toBeInTheDocument()
    expect(within(sidebar()).getByRole('button', { name: /Job posting review/ })).toBeInTheDocument()
  })
})
