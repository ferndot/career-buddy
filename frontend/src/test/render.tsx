import { fireEvent, render, screen, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AppProviders } from '../app'
import { AppShell } from '../app/AppShell'

export function renderApp(ui: ReactElement, route = '/') {
  return render(
    <AppProviders>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AppProviders>,
  )
}

/** `ui` as a page inside the app shell: with the header's Logs button and the activity sidebar. */
export function renderShell(ui: ReactElement, route = '/') {
  return renderApp(
    <Routes>
      <Route element={<AppShell />}>
        <Route path="*" element={ui} />
      </Route>
    </Routes>,
    route,
  )
}

/** Opens the sidebar from the header's Logs button, and one activity's stream when `activity` is given. */
export function openLogs(activity?: string | RegExp) {
  if (!screen.queryByRole('complementary', { name: 'Activity' })) fireEvent.click(screen.getByRole('button', { name: 'Logs' }))
  if (activity) fireEvent.click(within(screen.getByRole('complementary', { name: 'Activity' })).getByRole('button', { name: activity }))
}
