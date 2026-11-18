import type { TemplateLayout } from '../documents/api'
import type { SlotDoc, SlotLine } from './layout'

/**
 * The freeform sheet: the whole document as one piece of rich text in the template's own markup (header, `.cols`, `.main`, `.side`,
 * h2, h3, p, ul/li), so the template's CSS draws it as the output looks. Pure: the editor component only hosts it.
 *
 * What an edit means, in the saved document's overrides (see domain/slots.py):
 * - a changed line is the override of its slot id, as before;
 * - a line added after a slot is a further line of that slot's override, separated by a newline (it prints as a line of the same kind);
 * - a removed line is its slot's override left blank.
 * A moved line is a removal and an addition.
 */

/** The text of a slot the writer wrote, which the person may edit. Headings are the facts' own words: they can be removed, not reworded. */
export const editable = (slot: string) => slot === 'summary' || slot.startsWith('skills') || ['bullet:', 'edu:', 'para:'].some((p) => slot.startsWith(p))

const lines = (doc: SlotDoc): SlotLine[] =>
  doc.sections.flatMap((s) => s.entries.flatMap((e) => [e.heading, e.paragraph, ...e.bullets])).filter((l): l is SlotLine => !!l)

/** Every slot the sheet can change: its editable lines and its headings, with the text each has before any edit. */
export const sheetDefaults = (doc: SlotDoc, defaults: Record<string, string>) =>
  Object.fromEntries(lines(doc).map((l) => [l.slot, defaults[l.slot] ?? l.text]))

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** One slot as elements: its first line carries the slot id, any further line of its text is an element without one. */
function elements(tag: 'p' | 'li' | 'h3', slot: string, text: string, own: boolean): string {
  if (own && !text) return '' // removed
  const parts = text.split('\n')
  const fixed = tag === 'h3' ? ' contenteditable="false"' : ''
  return parts.map((t, i) => `<${tag}${i ? '' : ` data-slot="${esc(slot)}"`}${fixed}>${esc(t)}</${tag}>`).join('')
}

/** The document's html for the editor, from the defaults and the user's overrides. */
export function sheetHtml(doc: SlotDoc, layout: TemplateLayout, defaults: Record<string, string>, overrides: Record<string, string>): string {
  const text = (l: SlotLine) => overrides[l.slot] ?? defaults[l.slot] ?? l.text
  const line = (tag: 'p' | 'li' | 'h3', l: SlotLine) => elements(tag, l.slot, text(l), l.slot in overrides)
  const main: string[] = []
  const side: string[] = []
  for (const s of doc.sections) {
    const into = layout.side.includes(s.title) ? side : main
    if (s.title) into.push(`<h2 contenteditable="false">${esc(s.title)}</h2>`)
    for (const e of s.entries) {
      if (e.heading) into.push(line('h3', e.heading))
      if (e.paragraph) into.push(line('p', e.paragraph))
      if (e.bullets.length) into.push(`<ul>${e.bullets.map((b) => line('li', b)).join('')}</ul>`)
    }
  }
  const head = `<header class="${layout.header}" contenteditable="false"><h1>${esc(doc.name.text)}</h1>${doc.intro.map((l) => `<p>${esc(l.text)}</p>`).join('')}</header>`
  const columns = `<div class="main">${main.join('')}</div>${side.length ? `<div class="side">${side.join('')}</div>` : ''}`
  return `${head}<div class="cols">${columns}</div>`
}

const clean = (el: Element) => (el.textContent ?? '').replace(/\s+/g, ' ').trim()

/**
 * The overrides after the person edited the sheet. The first element carrying a slot id is that slot (a browser copies the id when a
 * line is split with Enter, so a repeat is an added line, as is any element without one). A slot with no element was removed.
 * A text equal to its default is no override. Overrides of slots the sheet does not hold are kept.
 *
 * shortcut: a line added right under a heading goes to the next line of its section, and one with nothing after it is dropped; upgrade if sections need empty items.
 */
export function readEdits(host: Element, doc: SlotDoc, defaults: Record<string, string>, overrides: Record<string, string>): Record<string, string> {
  const all = sheetDefaults(doc, defaults)
  const got: Record<string, string[]> = {}
  let last = '' // the slot whose text a new line continues
  let front: string[] = [] // new lines waiting for the next slot
  host.querySelectorAll('.cols h2, .cols h3, .cols p, .cols li').forEach((el) => {
    const slot = el.getAttribute('data-slot') ?? ''
    if (el.tagName !== 'P' && el.tagName !== 'LI') {
      if (el.tagName === 'H3' && slot && !(slot in got)) got[slot] = [clean(el)]
      last = ''
      front = el.tagName === 'H2' ? [] : front
      return
    }
    const text = clean(el)
    if (slot && !(slot in got)) {
      got[slot] = [...front, text]
      front = []
      last = slot
    } else if (text) {
      if (last) got[last].push(text)
      else front.push(text)
    }
  })
  const out = { ...overrides }
  for (const slot of Object.keys(all)) {
    delete out[slot]
    const text = (got[slot] ?? []).filter(Boolean).join('\n')
    if (text !== all[slot]) out[slot] = text
  }
  return out
}

/** `css` with every selector under `scope`; `body` is the scope itself. For the template's own CSS, which is written for the page. */
export const scopeCss = (css: string, scope: string) =>
  css.replace(/([^{}]+)\{([^{}]*)\}/g, (_, sel: string, body: string) =>
    `${sel.split(',').map((s) => (s.trim() === 'body' ? scope : `${scope} ${s.trim()}`)).join(',')}{${body}}`)

// The page's base rules (adapters/outputs/render_html.py), with the list and weight the app's CSS reset removes put back.
const BASE =
  'font-family:Helvetica,Arial,sans-serif;font-size:11pt;line-height:1.35;background:#fff;color:#1a1a1a;padding:1rem;outline:none}' +
  '.sheet h1{font-size:20pt;margin:0;font-weight:bold}.sheet h2{font-size:13pt;margin:1rem 0 .3rem;font-weight:bold}' +
  '.sheet h3{font-size:11pt;margin:.6rem 0 .2rem;font-weight:bold}.sheet p{margin:.2rem 0}' +
  '.sheet ul{margin:.2rem 0;padding-left:1.2rem;list-style:disc}[data-slot]:empty{min-height:1.35em;background:#f6f7f9}'

/** The sheet's CSS: the base rules, then the template's own, then the ATS rule the output ends with. */
export const sheetCss = (layout: TemplateLayout) => `.sheet{${BASE}${scopeCss(layout.css, '.sheet')}.sheet h2{text-transform:none}`
