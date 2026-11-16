import { screen } from '@testing-library/react'
import { renderApp } from '../test/render'
import { AppRoutes } from './routes'

describe('AppShell', () => {
  it('renders the four nav links with correct hrefs', () => {
    renderApp(<AppRoutes />, '/sources')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    const links = Array.from(nav.querySelectorAll('a')).map((a) => [a.textContent, a.getAttribute('href')])
    expect(links).toEqual([
      ['Sources', '/sources'],
      ['Career', '/career'],
      ['Documents', '/documents'],
      ['Settings', '/settings'],
    ])
  })

  it('redirects / to Sources and marks it as current', () => {
    renderApp(<AppRoutes />, '/')
    expect(screen.getByRole('heading', { level: 1, name: 'Sources' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sources' })).toHaveAttribute('aria-current', 'page')
  })

  it('renders /documents/new', () => {
    renderApp(<AppRoutes />, '/documents/new')
    expect(screen.getByRole('heading', { level: 1, name: 'New document' })).toBeInTheDocument()
  })
})
