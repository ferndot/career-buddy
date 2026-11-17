import type { DocLine, GenSection, GenText, PreviewDoc } from '../documents/api'
import type { DocDraft } from './state'

/** A line of the preview with the id of the slot it fills in a saved layout (the backend's domain/written.py numbers them). */
export type SlotLine = DocLine & { slot: string }
export type SlotEntry = { heading: SlotLine | null; paragraph: SlotLine | null; bullets: SlotLine[] }
export type SlotDoc = { name: SlotLine; intro: SlotLine[]; sections: { title: string; entries: SlotEntry[] }[] }

const line = (slot: string, t: Pick<GenText, 'text'> & Partial<GenText>, source: string | null = null): SlotLine =>
  ({ slot, text: t.text, source_fact_id: source, origin: 'suggestion', field: '', cites: t.fact_ids ?? [] })

/**
 * One section of the writer's document as the sheet draws it: a position is its heading and bullets; any other item is a paragraph.
 * A company's condensed positions are one heading line each, and the item's bullets come after the last (as the backend prints them).
 */
function entries(s: GenSection): SlotEntry[] {
  return s.items.flatMap((i): SlotEntry[] => {
    if (s.key !== 'experience') return [{ heading: null, paragraph: line(i.slot, i), bullets: [] }]
    const held = [i.position_id, ...i.also]
    const heading = (id: string, n: number) => line(`heading:${id}`, { text: n ? i.also_headings[n - 1] ?? '' : i.heading }, id)
    return held.map((id, n) => ({ heading: heading(id, n), paragraph: null, bullets: n === held.length - 1 ? i.bullets.map((b) => line(b.slot, b)) : [] }))
  })
}

/**
 * A new draft where the writer's text for a slot the user wrote comes back blank: the slot keeps the text it had before, so Reset to
 * generated still has something to go back to.
 */
export function keepPinned(draft: GenSection[], before: GenSection[], overrides: Record<string, string>): GenSection[] {
  const old = Object.fromEntries(before.flatMap((s) => s.items.flatMap((i) => [i, ...i.bullets])).map((t) => [t.slot, t.text]))
  const keep = <T extends GenText>(t: T): T => (t.slot in overrides && !t.text && old[t.slot] ? { ...t, text: old[t.slot] } : t)
  return draft.map((s) => ({ ...s, items: s.items.map((i) => ({ ...keep(i), bullets: i.bullets.map(keep) })) }))
}

/**
 * What one document shows: the template's header (name and contact lines, from the facts) and the writer's sections, in the writer's
 * order, with the default text of each slot. A letter is one untitled block of paragraphs. Nothing is shown from the facts' own
 * sections: the document is what the writer wrote, so a document nobody has written yet shows only the header.
 */
export function shown(preview: PreviewDoc, d: Pick<DocDraft, 'sections'>): { doc: SlotDoc; defaults: Record<string, string> } {
  const name = line('name', preview.name)
  const intro = preview.intro.map((l, n) => line(`intro:${n + 1}`, l))
  const sections = d.sections.map((s) => ({ title: s.key === 'body' ? '' : s.title, entries: entries(s) }))
  const defaults = Object.fromEntries(sections.flatMap((s) => s.entries.flatMap((e) => [e.paragraph, ...e.bullets])).filter((l): l is SlotLine => !!l).map((l) => [l.slot, l.text]))
  return { doc: { name, intro, sections }, defaults }
}
