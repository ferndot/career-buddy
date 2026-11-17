import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { DOCS_QUESTION } from './DocsStep'
import { stubReview } from './reviewStub'
import { openAt, stubApi } from './wizardStub'

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

const nextButton = () => screen.getByRole('button', { name: 'Next' })

test('step 2 asks in a bubble below the robot and lets several documents be chosen', async () => {
  stubApi()
  await openAt(2)
  const question = screen.getByText(DOCS_QUESTION)
  const robot = document.querySelector('svg[data-mascot]')!
  expect(robot.compareDocumentPosition(question) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy() // below, not beside
  expect(getComputedStyle(robot.parentElement!).flexDirection).toBe('column')

  expect(nextButton()).toBeDisabled()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Cover letter' }))
  expect(screen.getByRole('checkbox', { name: 'Resume' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Cover letter' })).toBeChecked()
  expect(nextButton()).toBeEnabled()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  expect(nextButton()).toBeEnabled() // one is enough
  fireEvent.click(screen.getByRole('checkbox', { name: 'Cover letter' }))
  expect(nextButton()).toBeDisabled()
})

test('the chosen documents become side tabs in steps 3 to 5, and not before', async () => {
  stubApi()
  await openAt(2)
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Cover letter' }))
  fireEvent.click(nextButton())
  await screen.findByLabelText('SQL')
  const tabs = () => screen.getAllByRole('tab').map((t) => t.textContent?.split(/Facts|Template|Saved/)[0])
  expect(tabs()).toEqual(['Resume', 'Cover letter'])
  expect(screen.getByRole('tab', { name: /Resume/ })).toHaveAttribute('aria-selected', 'true')
  await waitFor(() => expect(nextButton()).toBeEnabled())
  expect(screen.getByRole('tab', { name: /Resume/ })).toHaveTextContent('Facts done') // progress shows on the tab
  fireEvent.click(nextButton())
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 4 of 5 · Template')
  expect(tabs()).toEqual(['Resume', 'Cover letter'])
  fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
  expect(screen.getByRole('tab', { name: /Cover letter/ })).toHaveAttribute('aria-selected', 'true')
  expect(nextButton()).toBeDisabled() // the letter needs a role and company
  fireEvent.change(await screen.findByLabelText(/role/i), { target: { value: 'Engineer' } })
  fireEvent.change(screen.getByLabelText(/company/i), { target: { value: 'Acme' } })
  expect(nextButton()).toBeEnabled()
  fireEvent.click(nextButton())
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 5 of 5 · Download')
  expect(tabs()).toEqual(['Resume', 'Cover letter'])
})

test('a requirement the career lacks asks Do you have it: No records it and moves on', async () => {
  const calls = stubApi()
  stubReview({ must_have: ['Python', 'Kubernetes', 'Terraform'], missing_must_have: ['Kubernetes', 'Terraform'] })
  await openAt(3)
  expect(await screen.findByText('Do you have Kubernetes?')).toBeInTheDocument()
  expect(screen.getByText('Do you have Terraform?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'No, Terraform' }))
  expect(screen.queryByText('Do you have Terraform?')).not.toBeInTheDocument()
  expect(screen.getByText('Not in your career: Terraform.')).toBeInTheDocument()
  expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/facts'))).toBe(false) // No creates nothing
})

test('the review is asked about the posting only, and only the requirements the facts lack are listed', async () => {
  stubApi()
  const posted = stubReview({ must_have: ['Python', 'Terraform'], missing_must_have: ['Terraform'] })
  await openAt(3)
  expect(await screen.findByText('Do you have Terraform?')).toBeInTheDocument()
  expect(screen.queryByText('Do you have Python?')).not.toBeInTheDocument() // a must-have the facts cover is not asked
  expect(posted).toEqual([{ job_text: 'Python engineer with Kubernetes' }])
})

test('nice-to-have requirements sit in a separate group that starts collapsed', async () => {
  stubApi()
  stubReview({ missing_must_have: ['Terraform'], missing_nice_to_have: ['Rust'] })
  await openAt(3)
  const group = (await screen.findByText('Nice to have (1)')).closest('details')!
  expect(group).not.toHaveAttribute('open')
  expect(group).toContainElement(screen.getByText('Do you have Rust?'))
  expect(group).not.toContainElement(screen.getByText('Do you have Terraform?'))
})

test('without a model the pane suggests nothing and links to Settings', async () => {
  stubApi(['Kubernetes', 'Terraform']) // even the preview names missing terms: they are no longer used
  stubReview('unavailable')
  await openAt(3)
  expect(await screen.findByText(/Connect a model in/)).toHaveTextContent('Connect a model in Settings to check the job posting for requirements.')
  expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  expect(screen.queryByText(/Do you have/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Nice to have/)).not.toBeInTheDocument()
  await waitFor(() => expect(nextButton()).toBeEnabled()) // the facts are still chosen and the wizard goes on
})

test('Yes opens the skill form with the requirement filled in, and adds it as a skill fact', async () => {
  const calls = stubApi()
  stubReview({ missing_must_have: ['Kubernetes'] })
  await openAt(3)
  fireEvent.click(await screen.findByRole('button', { name: 'Yes, Kubernetes' }))
  const name = await screen.findByPlaceholderText('TypeScript')
  expect(name).toHaveValue('Kubernetes')
  expect(screen.getByText('Category')).toBeInTheDocument()
  expect(screen.getByText('Level')).toBeInTheDocument()
  expect(screen.getByText('Years')).toBeInTheDocument()
  fireEvent.change(screen.getByPlaceholderText('5'), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add skill' }))
  await waitFor(() => expect(screen.queryByText('Do you have Kubernetes?')).not.toBeInTheDocument())
  const post = calls.find((c) => c.method === 'POST' && c.url.endsWith('/api/facts'))
  expect(post?.body).toMatchObject({ kind: 'Skill', title: 'Kubernetes', parent_id: 'person', attributes: { years: '3' } })
})

test('step 4 edits are overrides on the document: reset to generated removes them', async () => {
  const calls = stubApi()
  await openAt(4)
  const bullet = await screen.findByLabelText('Edit text: Shipped it')
  expect(screen.queryByLabelText('Edit text: Engineer, Acme')).not.toBeInTheDocument() // headings are not editable
  fireEvent.change(bullet, { target: { value: 'Shipped it to 1M users' } })
  expect(screen.getByLabelText('Edit text: Shipped it')).toHaveValue('Shipped it to 1M users')
  fireEvent.click(screen.getByRole('button', { name: 'Reset to generated: Shipped it' }))
  expect(screen.getByLabelText('Edit text: Shipped it')).toHaveValue('Shipped it')
  expect(screen.queryByRole('button', { name: /Reset to generated/ })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Edit text: Builds things'), { target: { value: 'Builds reliable things' } })
  fireEvent.change(screen.getByLabelText('Edit text: Shipped it'), { target: { value: 'Shipped it to 1M users' } })
  fireEvent.click(nextButton())
  fireEvent.click(await screen.findByRole('button', { name: 'Save without downloading' }))
  await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/saved-documents'))).toBe(true))
  const save = calls.find((c) => c.method === 'POST' && c.url.endsWith('/api/saved-documents'))!
  expect(save.body).toMatchObject({
    template: 'resume-classic', skill_ids: ['s1', 's2'], education_ids: ['e1'], selection: ['b1'],
    overrides: { 'bullet:b1': 'Shipped it to 1M users', summary: 'Builds reliable things', headline: 'Engineer' },
  })
  expect(save.body).not.toHaveProperty('format')
  const previews = calls.filter((c) => c.url.includes('preview') && c.body?.template === 'resume-classic')
  for (const p of previews) expect(p.body?.overrides ?? {}).not.toHaveProperty('bullet:b1') // the preview shows generated text
})

test('step 5 offers Word, PDF and Text; saving happens once and shows the celebration', async () => {
  const calls = stubApi()
  await openAt(5)
  expect(screen.getByRole('button', { name: 'Word' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Text' })).toBeInTheDocument()
  expect(document.querySelector('svg[data-mascot="celebrate"]')).not.toBeInTheDocument() // nothing saved yet
  fireEvent.click(screen.getByRole('button', { name: 'Text' }))
  await waitFor(() => expect(calls.map((c) => `${c.method} ${c.url}`)).toContain('GET /api/saved-documents/d1/file?format=txt'))
  expect(await screen.findByText('Resume saved to your documents')).toBeInTheDocument()
  expect(document.querySelector('svg[data-mascot="celebrate"]')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'PDF' }))
  await waitFor(() => expect(calls.map((c) => c.url)).toContain('/api/saved-documents/d1/file?format=pdf'))
  expect(calls.filter((c) => c.method === 'POST' && c.url.endsWith('/api/saved-documents'))).toHaveLength(1)
})

test('each chosen document has its own download tab with the same format choices', async () => {
  stubApi()
  await openAt(5, ['Resume', 'Cover letter'])
  fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
  expect(screen.getByRole('group', { name: 'Download format for Cover letter' })).toBeInTheDocument()
  for (const name of ['Word', 'PDF', 'Text']) expect(screen.getByRole('button', { name })).toBeInTheDocument()
})
