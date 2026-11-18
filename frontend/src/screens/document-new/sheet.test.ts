import { expect, test } from 'vitest'
import type { TemplateLayout } from '../documents/api'
import type { SlotDoc, SlotLine } from './layout'
import { readEdits, scopeCss, sheetCss, sheetHtml } from './sheet'

const l = (slot: string, text: string): SlotLine => ({ slot, text, source_fact_id: null, origin: 'suggestion', field: '', cites: [] })
const doc: SlotDoc = {
  name: l('name', 'Ada'),
  intro: [l('intro:1', 'London')],
  sections: [
    { title: 'Experience', entries: [{ heading: l('heading:p1', 'Engineer, Acme'), paragraph: null, bullets: [l('bullet:a', 'Built A'), l('bullet:b', 'Built B')] }] },
    { title: 'Skills', entries: [{ heading: null, paragraph: l('skills', 'Python'), bullets: [] }] },
  ],
}
const layout: TemplateLayout = { header: 'plain', side: ['Skills'], css: 'header{background:#1f3a5f}body{font-size:10pt}h2{color:#2b5c8a}', accent: '#2b5c8a', panel: '#f2f4f7' }
const defaults = { 'bullet:a': 'Built A', 'bullet:b': 'Built B', skills: 'Python' }
const host = (overrides: Record<string, string> = {}) => {
  const el = document.createElement('div')
  el.innerHTML = sheetHtml(doc, layout, defaults, overrides)
  return el
}
const read = (el: Element, overrides: Record<string, string> = {}) => readEdits(el, doc, defaults, overrides)

test('the sheet is the template markup: header, columns with the side headings apart, fixed titles and headings', () => {
  const el = host()
  expect(el.querySelector('header.plain h1')?.textContent).toBe('Ada')
  expect(el.querySelector('.main h2')?.textContent).toBe('Experience')
  expect(el.querySelector('.side h2')?.textContent).toBe('Skills')
  expect(el.querySelector('h3')).toHaveAttribute('contenteditable', 'false')
  expect([...el.querySelectorAll('li')].map((x) => x.textContent)).toEqual(['Built A', 'Built B'])
})

test('an untouched sheet is no override at all, and earlier overrides come back as they were', () => {
  expect(read(host())).toEqual({})
  const own = { 'bullet:a': 'Mine\nExtra', 'bullet:b': '' }
  expect(read(host(own), own)).toEqual(own) // what is saved renders and reads back the same: two lines, one removed
})

test('an edited line, an added line and a removed line become overrides keyed by slot', () => {
  const el = host()
  const [a, b] = [...el.querySelectorAll('li')]
  a.textContent = 'Built A faster'
  const added = b.cloneNode() as HTMLElement // Enter copies the slot id
  added.textContent = 'Built C'
  b.after(added)
  expect(read(el)).toEqual({ 'bullet:a': 'Built A faster', 'bullet:b': 'Built B\nBuilt C' })
  added.remove()
  b.remove()
  expect(read(el)).toEqual({ 'bullet:a': 'Built A faster', 'bullet:b': '' })
})

test('a line moved is a removal and an addition: cut from one place, pasted as text in another', () => {
  const el = host()
  const [a, b] = [...el.querySelectorAll('li')]
  b.remove()
  const pasted = a.cloneNode() as HTMLElement
  pasted.textContent = 'Built B'
  a.after(pasted)
  expect(read(el)).toEqual({ 'bullet:a': 'Built A\nBuilt B', 'bullet:b': '' })
})

test('a line added under a heading belongs to the next line of its section, and a removed heading is removed', () => {
  const el = host()
  const first = el.querySelector('li')!
  const fresh = document.createElement('li')
  fresh.textContent = 'Opened with this'
  first.parentElement!.before(fresh) // between the heading and the list's first line
  expect(read(el)).toEqual({ 'bullet:a': 'Opened with this\nBuilt A' })
  el.querySelector('h3')!.remove()
  expect(read(el)['heading:p1']).toBe('')
})

test('the template CSS is scoped to the sheet and keeps its colours', () => {
  expect(scopeCss('header p,h2{color:#fff}body{font-size:10pt}', '.sheet')).toBe('.sheet header p,.sheet h2{color:#fff}.sheet{font-size:10pt}')
  const css = sheetCss(layout)
  expect(css).toContain('.sheet header{background:#1f3a5f}') // the template's band
  expect(css).toContain('.sheet h2{color:#2b5c8a}')
  expect(css.endsWith('.sheet h2{text-transform:none}')).toBe(true) // as the output: headings are not printed in capitals
})
