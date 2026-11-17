import { expect, test } from 'vitest'
import type { GenItem, GenSection, PreviewDoc } from '../documents/api'
import { shown } from './layout'

const text = (slot: string, t: string, fact_ids: string[]) => ({ slot, text: t, fact_ids })
const item = (x: Partial<GenItem>): GenItem => ({ slot: '', text: '', fact_ids: [], position_id: '', heading: '', also: [], also_headings: [], bullets: [], ...x })
const preview = { name: { text: 'Jane' }, intro: [] } as unknown as PreviewDoc
const sheet = (items: GenItem[]) => {
  const sections: GenSection[] = [{ key: 'experience', title: 'Experience', items }]
  return shown(preview, { sections }).doc.sections[0].entries.map((e) => [e.heading?.text, e.heading?.slot, e.bullets.map((b) => b.text)])
}

test('a condensed company is a heading line for each title and its one set of bullets after the last', () => {
  expect(sheet([item({ position_id: 'p1', heading: 'Senior Analyst, Acme (2021 - 2024)', also: ['p3'], also_headings: ['Analyst, Acme (2017 - 2021)'], bullets: [text('bullet:a1', 'Led it', ['a1']), text('bullet:c1', 'Built it', ['c1'])] })])).toEqual([
    ['Senior Analyst, Acme (2021 - 2024)', 'heading:p1', []],
    ['Analyst, Acme (2017 - 2021)', 'heading:p3', ['Led it', 'Built it']],
  ])
})

test('positions kept separate are one entry each with their own bullets', () => {
  expect(sheet([item({ position_id: 'p1', heading: 'Web Developer, Acme', bullets: [text('bullet:a1', 'Shipped it', ['a1'])] }), item({ position_id: 'p3', heading: 'Assistant Editor, Acme', bullets: [text('bullet:c1', 'Edited it', ['c1'])] })])).toEqual([
    ['Web Developer, Acme', 'heading:p1', ['Shipped it']],
    ['Assistant Editor, Acme', 'heading:p3', ['Edited it']],
  ])
})
