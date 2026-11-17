import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { openLogs, renderShell } from '../../test/render'
import { DOCS_QUESTION } from './DocsStep'
import { stubReview } from './reviewStub'
import { NewDocumentScreen } from './NewDocumentScreen'
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

test('the chosen documents become side tabs in steps 4 and 5, and not before', async () => {
  stubApi()
  await openAt(2)
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Cover letter' }))
  fireEvent.click(nextButton())
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 3 of 5 · Missing requirements')
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument() // what the posting needs is asked once, not per document
  fireEvent.click(nextButton())
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 4 of 5 · Template and preview')
  const tabs = () => screen.getAllByRole('tab').map((t) => t.textContent?.split(/Template|Saved/)[0])
  expect(tabs()).toEqual(['Resume', 'Cover letter'])
  expect(screen.getByRole('tab', { name: /Resume/ })).toHaveAttribute('aria-selected', 'true')
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

test('the wizard has five steps and none of them picks facts', async () => {
  stubApi()
  stubReview({ must_have: ['Python'] })
  await openAt(3)
  expect(screen.getByLabelText('Progress')).toHaveTextContent('Step 3 of 5 · Missing requirements')
  expect(await screen.findByText('Your career covers every requirement in the posting.')).toBeInTheDocument()
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0) // no skill, bullet or education to tick
  expect(screen.queryByLabelText('Headline')).not.toBeInTheDocument()
  expect(nextButton()).toBeEnabled()
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
  expect(within(screen.getByRole('main')).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  expect(screen.queryByText(/Do you have/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Nice to have/)).not.toBeInTheDocument()
  expect(nextButton()).toBeEnabled() // nothing to answer: the wizard goes on
})

test('Yes opens the skill form with the requirement filled in, and adds it as a skill fact', async () => {
  const calls = stubApi()
  stubReview({ missing_must_have: ['Kubernetes'] })
  await openAt(3)
  const yes = await screen.findByRole('button', { name: 'Yes, Kubernetes' })
  await waitFor(() => expect(yes).toBeEnabled()) // the person fact is still loading when the review is already stored
  fireEvent.click(yes)
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
    template: 'resume-classic',
    overrides: { 'bullet:b1': 'Shipped it to 1M users', summary: 'Builds reliable things' },
  })
  for (const key of ['format', 'selection', 'skill_ids', 'education_ids']) expect(save.body).not.toHaveProperty(key)
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

// The model reads the posting when the user leaves step 1, not before.
const POSTING = 'Python engineer with Kubernetes'
const progress = () => screen.getByLabelText('Progress')
function pasteAt1(text = POSTING) {
  renderShell(<NewDocumentScreen />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: text } })
}

test('step 1 does not call /api/fit: the posting is only fetched or pasted', () => {
  stubApi()
  const posted = stubReview({})
  pasteAt1()
  expect(nextButton()).toBeEnabled()
  expect(posted).toEqual([])
})

test('Next shows the Fetching job description page, calls /api/fit once, then goes to step 2', async () => {
  stubApi()
  let release = () => {}
  const posted = stubReview({ missing_must_have: ['Kubernetes'] }, new Promise<void>((r) => (release = r)))
  pasteAt1()
  fireEvent.click(nextButton())
  expect(await screen.findByText('Fetching job description')).toBeInTheDocument()
  expect(screen.getByText('Reading the posting for requirements.')).toBeInTheDocument()
  expect(document.querySelector('svg[data-mascot="thinking"]')).toBeInTheDocument()
  expect(progress()).toHaveTextContent('Step 1 of 5 · Job posting') // a transition, not a numbered step
  expect(nextButton()).toBeDisabled()
  expect(posted).toEqual([{ job_text: POSTING }])
  release()
  await screen.findByRole('checkbox', { name: 'Resume' })
  expect(progress()).toHaveTextContent('Step 2 of 5 · Documents')
  expect(screen.queryByText('Fetching job description')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(nextButton())
  expect(await screen.findByText('Do you have Kubernetes?')).toBeInTheDocument() // step 3 reads the stored review
  expect(posted).toHaveLength(1)
})

test('with no model (503) the user goes on to step 2 and step 3 links to Settings', async () => {
  stubApi()
  const posted = stubReview('unavailable')
  await openAt(2)
  expect(progress()).toHaveTextContent('Step 2 of 5 · Documents')
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(nextButton())
  expect(screen.getByText(/Connect a model in/)).toHaveTextContent('Connect a model in Settings to check the job posting for requirements.')
  expect(posted).toHaveLength(1)
  openLogs(/Job posting review/)
  expect(within(screen.getByRole('log')).getByText(/No answer from the model: Connect a model in Settings/)).toBeInTheDocument()
})

test('another failure keeps the page up: Try again reads the posting, Continue without requirements goes on', async () => {
  stubApi()
  stubReview('error')
  pasteAt1()
  fireEvent.click(nextButton())
  expect(await screen.findByText('Could not read the posting for requirements.')).toBeInTheDocument()
  expect(screen.getByText('Fetching job description')).toBeInTheDocument()
  expect(progress()).toHaveTextContent('Step 1 of 5 · Job posting')
  stubReview({ missing_must_have: ['Kubernetes'] })
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  await screen.findByRole('checkbox', { name: 'Resume' })
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(nextButton())
  expect(await screen.findByText('Do you have Kubernetes?')).toBeInTheDocument()
})

test('Continue without requirements stores no review and step 3 says to connect a model', async () => {
  stubApi()
  stubReview('error')
  pasteAt1()
  fireEvent.click(nextButton())
  fireEvent.click(await screen.findByRole('button', { name: 'Continue without requirements' }))
  await screen.findByRole('checkbox', { name: 'Resume' })
  fireEvent.click(screen.getByRole('checkbox', { name: 'Resume' }))
  fireEvent.click(nextButton())
  expect(screen.getByText(/Connect a model in/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  expect(screen.getByLabelText('Job posting link')).toBeInTheDocument() // back on step 1, not on the error page
})

test('a changed posting is read again on Next; an unchanged one reuses the stored review', async () => {
  stubApi()
  const posted = stubReview({})
  await openAt(2)
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  fireEvent.click(nextButton())
  await screen.findByRole('checkbox', { name: 'Resume' })
  expect(posted).toHaveLength(1) // same text: no second review
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  fireEvent.click(screen.getByRole('button', { name: 'Paste the job text instead' }))
  fireEvent.change(screen.getByLabelText('Job posting text'), { target: { value: 'Rust engineer' } })
  fireEvent.click(nextButton())
  await screen.findByRole('checkbox', { name: 'Resume' })
  expect(posted).toEqual([{ job_text: POSTING }, { job_text: 'Rust engineer' }])
})
