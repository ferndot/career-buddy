import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { findLine, openAt, stubApi } from './wizardStub'

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

const generate = () => fireEvent.click(screen.getByRole('button', { name: 'Next' }))
const sentToWriter = (calls: ReturnType<typeof stubApi>) => calls.filter((c) => c.url.endsWith('/api/documents/generate')).map((c) => c.body)

test('step 4 shows the layout as bars: the section headings and the template, none of the facts text', async () => {
  stubApi()
  await openAt(4)
  const sheet = await screen.findByTestId('wireframe')
  expect(sheet).toHaveAccessibleName('Layout of the Classic resume')
  expect(sheet.querySelectorAll('[data-testid="bar"]').length).toBeGreaterThan(8)
  for (const heading of ['Summary', 'Experience', 'Education', 'Skills']) expect(sheet).toHaveTextContent(heading)
  expect(sheet).not.toHaveTextContent(/Ada|Builds things|Shipped it|Engineer, Acme/)
  expect(screen.queryByText('Builds things')).not.toBeInTheDocument()
})

test('step 4 has no ATS check', async () => {
  stubApi()
  await openAt(4)
  await screen.findByTestId('wireframe')
  expect(screen.queryByText('ATS check')).not.toBeInTheDocument()
})

test('the wireframe follows the chosen template, and a letter has its styles', async () => {
  stubApi()
  await openAt(4)
  fireEvent.click(screen.getByRole('radio', { name: 'Sidebar resume' }))
  expect(await screen.findByTestId('wireframe')).toHaveAccessibleName('Layout of the Sidebar resume')
  expect(screen.queryByRole('radiogroup', { name: 'Writing style' })).not.toBeInTheDocument()
})

test('step 5 is headed by the document title and shows the text on a white sheet', async () => {
  stubApi()
  await openAt(5)
  expect(await screen.findByRole('heading', { name: 'Resume - Ada' })).toBeInTheDocument()
  const sheet = screen.getByRole('textbox', { name: 'Edit the Resume - Ada' }) // one editable sheet for the whole document
  expect(sheet).toHaveAttribute('contenteditable', 'true')
  expect(within(sheet).getByText('Generated summary')).toBeInTheDocument()
  expect(screen.getByText('ATS check')).toBeInTheDocument()
  expect(screen.queryByText('Preview')).not.toBeInTheDocument()
})

test('a cover letter is titled with the company from the posting review', async () => {
  stubApi([], true, undefined, { title: 'Platform Engineer', company: 'Initech' })
  await openAt(5, ['Resume', 'Cover letter'])
  fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
  expect(await screen.findByRole('heading', { name: 'Cover letter - Initech' })).toBeInTheDocument()
})

test('the writer is sent the instructions of the chosen template', async () => {
  const calls = stubApi()
  await openAt(4)
  fireEvent.click(screen.getByRole('radio', { name: 'Sidebar resume' }))
  generate()
  await findLine('Generated summary')
  expect(sentToWriter(calls).map((b) => [b?.template, b?.template_instructions])).toEqual([['resume-sidebar', 'Sidebar style.']])
})

test('a letter is written in the chosen style: the template instructions then the style instructions, kept with the save', async () => {
  const calls = stubApi()
  await openAt(4, ['Cover letter'])
  expect(screen.getByRole('radio', { name: 'Direct and concise' })).toBeChecked()
  fireEvent.click(screen.getByRole('radio', { name: 'Narrative story' }))
  expect(screen.getByRole('radio', { name: 'Narrative story' })).toBeChecked()
  generate()
  await findLine('Generated two')
  expect(sentToWriter(calls)[0]?.template_instructions).toBe('Letter style. Tell a story.')
  fireEvent.click(await screen.findByRole('button', { name: 'Save without downloading' }))
  await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/saved-documents'))).toBe(true))
  expect(calls.find((c) => c.method === 'POST' && c.url.endsWith('/api/saved-documents'))?.body?.template_instructions).toBe('Letter style. Tell a story.')
})

test('a template whose PDF was measured ATS-safe shows a badge; the others do not', async () => {
  stubApi()
  await openAt(4)
  expect(within(screen.getByRole('radio', { name: 'Classic resume' })).getByText('ATS-safe')).toBeInTheDocument()
  expect(within(screen.getByRole('radio', { name: 'Sidebar resume' })).queryByText('ATS-safe')).not.toBeInTheDocument()
})
