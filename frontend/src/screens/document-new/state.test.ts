import { expect, test } from 'vitest'
import { emptyDoc, initialWizard, buildSave, type Wizard } from './state'
import type { Template } from '../documents/api'

const t = { id: 'resume-classic', label: 'Classic resume', instructions: '', styles: [] } as unknown as Template
const wizard = (patch: Partial<Wizard>): Wizard => ({ ...initialWizard, kinds: ['resume'], docs: { resume: { ...emptyDoc, templateId: t.id }, letter: emptyDoc }, ...patch })

test('a save names the job from the posting review, with the listing link when the job came from one', () => {
  const w = wizard({ jobUrl: ' https://jobs.example.com/p/1 ', review: { text: 'x', result: { title: 'Data Platform Engineer', company: 'Contoso Data', must_have: [], nice_to_have: [], missing_must_have: [], missing_nice_to_have: [] } } })
  expect(buildSave(w, 'resume', t)).toMatchObject({ job_title: 'Data Platform Engineer', company: 'Contoso Data', job_url: 'https://jobs.example.com/p/1' })
})

test('without a review the role input names it, and pasted text saves no link', () => {
  const w = wizard({ docs: { resume: { ...emptyDoc, templateId: t.id, inputs: { role: 'Engineer' } }, letter: emptyDoc } })
  expect(buildSave(w, 'resume', t)).toMatchObject({ job_title: 'Engineer', company: '', job_url: '' })
  expect(buildSave(wizard({}), 'resume', t)).toMatchObject({ job_title: '', job_url: '' })
})
