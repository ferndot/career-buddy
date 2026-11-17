import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { queryClient } from '../../api'
import { MAX_INSTRUCTIONS } from '../documents/api'
import { openLogs } from '../../test/render'
import { DRAFTS, openAt, stubApi, type Calls } from './wizardStub'

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  queryClient.clear()
})

const post = (calls: Calls, suffix: string) => calls.filter((c) => c.method === 'POST' && c.url.endsWith(suffix))
const generate = () => fireEvent.click(screen.getByRole('button', { name: 'Generate text' }))
const directions = () => screen.getByLabelText('Directions for this document')
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

/** Next to the download step, saves without downloading, and returns the save request. */
async function saved(calls: Calls) {
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Save without downloading' }))
  await waitFor(() => expect(post(calls, '/api/saved-documents')).toHaveLength(1))
  return post(calls, '/api/saved-documents')[0].body!
}

test('generate sends the directions and shows the returned text as the default, not as an edit', async () => {
  const calls = stubApi()
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  expect(screen.getByText('Tell the writer what to emphasise or how to phrase it. Optional.')).toBeInTheDocument()
  fireEvent.change(directions(), { target: { value: 'Stress reliability' } })
  generate()
  expect(await screen.findByLabelText('Edit text: Generated summary')).toHaveValue('Generated summary')
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('Generated bullet')
  expect(post(calls, '/api/documents/generate')[0].body).toMatchObject({
    template: 'resume-classic', instructions: 'Stress reliability', pinned: [], resume_pages: 1,
  })
  for (const picked of ['selection', 'skill_ids', 'education_ids']) expect(post(calls, '/api/documents/generate')[0].body).not.toHaveProperty(picked) // every visible fact is used
  expect(screen.queryByText('Edited')).not.toBeInTheDocument() // generated text is a default: no override, nothing to reset
  expect(screen.queryByRole('button', { name: /Reset to generated/ })).not.toBeInTheDocument()
  const body = await saved(calls)
  expect(body.generated).toEqual({ summary: 'Generated summary', 'bullet:b1': 'Generated bullet' }) // kept apart from the user's own words
  expect(body.overrides).toEqual({})
  expect(body.instructions).toBe('Stress reliability')
})

test('a resume has its own length, one page until chosen, sent to the writer and kept with the saved document; a letter has none', async () => {
  const calls = stubApi()
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  const length = screen.getByLabelText('Resume length')
  expect(length).toHaveValue('1')
  fireEvent.change(length, { target: { value: '2' } })
  generate()
  await screen.findByLabelText('Edit text: Generated summary')
  expect(post(calls, '/api/documents/generate')[0].body).toMatchObject({ resume_pages: 2 })
  expect((await saved(calls)).resume_pages).toBe(2)
})

test('the cover letter tab has no length control and saves the default', async () => {
  const calls = stubApi()
  await openAt(4, ['Cover letter'])
  await screen.findByLabelText('Edit text: Paragraph one')
  expect(screen.queryByLabelText('Resume length')).not.toBeInTheDocument()
  expect((await saved(calls)).resume_pages).toBe(1)
})

test('an edit is an override keyed by slot id, reset removes it, and generated text is saved apart from it', async () => {
  const calls = stubApi()
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  const bullet = await screen.findByLabelText('Edit text: Generated bullet')
  fireEvent.change(bullet, { target: { value: 'My own bullet' } })
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('My own bullet')
  fireEvent.click(screen.getByRole('button', { name: 'Reset to generated: Generated bullet' }))
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('Generated bullet') // back to the generated text
  fireEvent.change(screen.getByLabelText('Edit text: Generated bullet'), { target: { value: 'My own bullet' } })
  const body = await saved(calls)
  expect(body.overrides).toEqual({ 'bullet:b1': 'My own bullet' })
  expect(body.generated).toEqual({ summary: 'Generated summary', 'bullet:b1': 'Generated bullet' })
})

test('generating again pins what the user wrote and replaces only the generated text around it', async () => {
  let n = 0
  const calls = stubApi([], true, () => json(n++ === 0 ? DRAFTS.resume : { slots: { summary: 'Second summary' }, cites: {}, flags: {} }))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  fireEvent.change(await screen.findByLabelText('Edit text: Generated bullet'), { target: { value: 'My own bullet' } })
  generate()
  expect(await screen.findByLabelText('Edit text: Second summary')).toHaveValue('Second summary')
  expect(post(calls, '/api/documents/generate')[1].body).toMatchObject({ pinned: ['bullet:b1'] })
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('My own bullet') // still the user's
  fireEvent.click(screen.getByRole('button', { name: 'Reset to generated: Generated bullet' }))
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('Generated bullet') // the earlier draft kept beneath it
})

test('a bullet the writer could not reword and a slot left empty are flagged with the reasons, until the user writes them', async () => {
  const draft = {
    slots: { summary: '', 'bullet:b1': 'Shipped it' },
    cites: {},
    flags: { summary: { code: 'rejected', reasons: ['number not in the source: 12'] }, 'bullet:b1': { code: 'not_rewritten', reasons: ['number not in the source: 90'] } },
  }
  stubApi([], true, () => json(draft))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  expect(await screen.findByText(/Not rewritten: .*number not in the source: 90/)).toBeInTheDocument()
  expect(screen.getByText(/Left empty: .*number not in the source: 12/)).toBeInTheDocument()
  expect(screen.getByLabelText('Edit text: summary')).toHaveValue('') // named by its id: there is no text to name it by
  expect(screen.getByLabelText('Edit text: Shipped it')).toHaveValue('Shipped it') // the fact's own words
  fireEvent.change(screen.getByLabelText('Edit text: summary'), { target: { value: 'My own summary' } })
  expect(screen.queryByText(/Left empty/)).not.toBeInTheDocument()
  expect(screen.getByText(/Not rewritten/)).toBeInTheDocument()
})

test('a draft the facts did not support is an error and the last draft stays', async () => {
  let n = 0
  stubApi([], true, () => (n++ === 0 ? json(DRAFTS.resume)
    : json({ detail: "The model's text did not match your facts closely enough. Your last draft is unchanged.", code: 'ungrounded', rejected: [] }, 502)))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  await screen.findByLabelText('Edit text: Generated summary')
  generate()
  expect(await screen.findByRole('alert')).toHaveTextContent('Your last draft is unchanged.')
  expect(screen.getByLabelText('Edit text: Generated summary')).toHaveValue('Generated summary')
  expect(screen.getByLabelText('Edit text: Generated bullet')).toHaveValue('Generated bullet')
})

test('a cover letter paragraph is editable; the saved letter carries every paragraph, the stub ones as generated text', async () => {
  const calls = stubApi()
  await openAt(4, ['Cover letter'])
  const para = await screen.findByLabelText('Edit text: Paragraph one')
  fireEvent.change(para, { target: { value: 'I would love to join Acme.' } })
  expect(screen.getByLabelText('Edit text: Paragraph one')).toHaveValue('I would love to join Acme.')
  const body = await saved(calls)
  expect(body.overrides).toEqual({ 'para:1': 'I would love to join Acme.' })
  expect(body.generated).toEqual({ 'para:1': 'Paragraph one', 'para:2': 'Paragraph two' })
})

test('a generated letter is its own paragraphs under the header', async () => {
  const calls = stubApi()
  await openAt(4, ['Cover letter'])
  await screen.findByLabelText('Edit text: Paragraph one')
  generate()
  expect(await screen.findByLabelText('Edit text: Generated two')).toBeInTheDocument()
  expect(screen.queryByLabelText('Edit text: Paragraph one')).not.toBeInTheDocument() // replaced, not overlaid
  fireEvent.change(screen.getByLabelText('Edit text: Generated two'), { target: { value: 'Second, mine' } })
  const body = await saved(calls)
  expect(body.overrides).toEqual({ 'para:2': 'Second, mine' })
  expect(body.generated).toEqual({ 'para:1': 'Generated one', 'para:2': 'Generated two', 'para:3': 'Generated three' })
})

test('without a model Generate is disabled and says where to connect one; text can still be edited by hand', async () => {
  const calls = stubApi([], false)
  await openAt(4)
  const bullet = await screen.findByLabelText('Edit text: Shipped it')
  expect(await screen.findByText(/Connect a model in/)).toHaveTextContent('Connect a model in Settings to generate text')
  expect(within(screen.getByRole('main')).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  expect(screen.getByRole('button', { name: 'Generate text' })).toBeDisabled()
  generate()
  expect(post(calls, '/api/documents/generate')).toHaveLength(0)
  fireEvent.change(bullet, { target: { value: 'By hand' } })
  expect(screen.getByLabelText('Edit text: Shipped it')).toHaveValue('By hand')
})

test('the directions box counts characters and stops Generate above 2000', async () => {
  const calls = stubApi()
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  fireEvent.change(directions(), { target: { value: 'x'.repeat(MAX_INSTRUCTIONS) } })
  expect(screen.getByText(`${MAX_INSTRUCTIONS} / ${MAX_INSTRUCTIONS}`)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Generate text' })).toBeEnabled()
  fireEvent.change(directions(), { target: { value: 'x'.repeat(MAX_INSTRUCTIONS + 1) } })
  expect(screen.getByRole('alert')).toHaveTextContent(`${MAX_INSTRUCTIONS + 1} / ${MAX_INSTRUCTIONS}`)
  expect(screen.getByRole('button', { name: 'Generate text' })).toBeDisabled()
  generate()
  expect(post(calls, '/api/documents/generate')).toHaveLength(0)
})

test('generating adds entries to the activity log: the request, the slots returned, and what was rejected and why', async () => {
  const draft = { ...DRAFTS.resume, flags: { 'bullet:b1': { code: 'not_rewritten', reasons: ['number not in the source: 90'] } } }
  stubApi([], true, () => json(draft))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  openLogs(/Job posting review/)
  expect(within(screen.getByRole('log')).getByText(/Reading the posting/)).toBeInTheDocument() // the review on the way here is already in the log
  fireEvent.click(screen.getByRole('button', { name: 'Back to all activities' }))
  generate()
  fireEvent.click(await screen.findByRole('button', { name: /Document: Resume/ })) // the writing is its own activity
  const log = screen.getByRole('log')
  expect(await within(log).findByText(/Received 2 slots/)).toBeInTheDocument()
  const lines = within(log).getAllByText(/Sent request|Received|rejected/).map((e) => e.textContent!.replace(/^\S+ /, ''))
  expect(lines).toEqual(['Sent request for the resume', 'Received 2 slots', '1 rejected: number not in the source: 90'])
  expect(screen.getByText('Done')).toBeInTheDocument()
})

test('the wizard has no Logs button of its own: the header one shows its activities from any step', async () => {
  stubApi([], true, () => json({}))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  expect(screen.getAllByRole('button', { name: 'Logs' })).toHaveLength(1)
  openLogs()
  expect(within(screen.getByRole('complementary', { name: 'Activity' })).getByRole('button', { name: /Job posting review/ })).toBeInTheDocument()
})

test('a failed generate is logged with its reason', async () => {
  stubApi([], true, () => json({ detail: 'The writer is busy.', code: 'x' }, 502))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  openLogs()
  fireEvent.click(await screen.findByRole('button', { name: /Document: Resume/ }))
  expect(await within(screen.getByRole('log')).findByText(/Failed: The writer is busy\./)).toBeInTheDocument()
  expect(screen.getByText('Failed')).toBeInTheDocument()
})

test('a failed generate keeps the document from going on until a generate works', async () => {
  let fail = true
  stubApi([], true, () => (fail ? json({ detail: 'The writer is busy.', code: 'x' }, 502) : json(DRAFTS.resume)))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled())
  fail = false
  generate()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled())
})

test('each generate press is its own activity in the log', async () => {
  stubApi([], true, () => json(DRAFTS.resume))
  await openAt(4)
  await screen.findByLabelText('Edit text: Shipped it')
  generate()
  generate()
  openLogs()
  const rows = await screen.findAllByRole('button', { name: /Document: Resume/ })
  expect(rows).toHaveLength(2)
  await waitFor(() => expect(screen.queryByText('Working')).not.toBeInTheDocument()) // both writes finish inside the test
})

test('a cover letter asks for no role or company: the posting review supplies them to the writer', async () => {
  const calls = stubApi([], true, undefined, { title: 'Platform Engineer', company: 'Initech' })
  await openAt(4, ['Cover letter'])
  fireEvent.click(screen.getByRole('tab', { name: /Cover letter/ }))
  await screen.findByLabelText('Edit text: Paragraph one')
  expect(screen.queryByLabelText(/role|company/i)).not.toBeInTheDocument()
  generate()
  await screen.findByLabelText('Edit text: Generated two')
  const sent = calls.find((c) => c.url.endsWith('/api/documents/generate') && c.body?.template === 'cover-letter')
  expect(sent?.body?.inputs).toEqual({ role: 'Platform Engineer', company: 'Initech' })
  expect(sent?.body?.job_text).toBe('Python engineer with Kubernetes')
})
