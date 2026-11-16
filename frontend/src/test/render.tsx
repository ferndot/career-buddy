import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { AppProviders } from '../app'

export function renderApp(ui: ReactElement, route = '/') {
  return render(
    <AppProviders>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AppProviders>,
  )
}
