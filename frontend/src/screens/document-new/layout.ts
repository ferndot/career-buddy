import type { DocLine, PreviewDoc } from '../documents/api'
import type { DocDraft, DocKind } from './state'

/** A line of the preview with the id of the slot it fills in a saved layout (the backend's domain/slots.py). */
export type SlotLine = DocLine & { slot: string }
export type SlotEntry = { heading: SlotLine | null; paragraph: SlotLine | null; bullets: SlotLine[] }
export type SlotDoc = { name: SlotLine; intro: SlotLine[]; sections: { title: string; entries: SlotEntry[] }[] }

type Role = 'name' | 'intro' | 'heading' | 'paragraph' | 'bullet'
const FACT_FIELDS = new Set(['title', 'location', 'headline', 'summary', 'skills', 'heading', 'label'])
const NAMED = new Set(['location', 'headline', 'summary', 'skills', 'greeting', 'closing', 'subject'])
const PARA = 'para:'

function slotId(role: Role, line: DocLine, taken: Set<string>): string {
  const fid = line.source_fact_id ?? ''
  const bound = FACT_FIELDS.has(line.field) && !!(fid || line.cites.length)
  const count = (prefix: string) => [...taken].filter((k) => k.startsWith(prefix)).length
  let base: string
  if (bound && line.field === 'title') base = role === 'name' ? 'name' : role === 'paragraph' ? 'signature' : `bullet:${fid}`
  else if (bound && line.field === 'heading') base = `heading:${fid}`
  else if (bound && line.field === 'label') base = `edu:${fid}`
  else if (NAMED.has(line.field)) base = line.field
  else if (role === 'name') base = 'name'
  else if (role === 'intro') base = `intro:${count('intro:') + 1}`
  else base = `${PARA}${count(PARA) + 1}`
  let id = base
  for (let n = 2; taken.has(id); n++) id = `${base}#${n}`
  taken.add(id)
  return id
}

/** The preview with slot ids, numbered in reading order exactly as the saved layout numbers them. */
export function slotDoc(doc: PreviewDoc): SlotDoc {
  const taken = new Set<string>()
  const mark = (role: Role, line: DocLine): SlotLine => ({ ...line, slot: slotId(role, line, taken) })
  const name = mark('name', doc.name)
  const intro = doc.intro.map((l) => mark('intro', l))
  const sections = doc.sections.map((s) => ({
    title: s.title,
    entries: s.entries.map((e) => ({
      heading: e.heading && mark('heading', e.heading),
      paragraph: e.paragraph && mark('paragraph', e.paragraph),
      bullets: e.bullets.map((b) => mark('bullet', b)),
    })),
  }))
  return { name, intro, sections }
}

const paraNumbers = (keys: string[]) => keys.filter((k) => k.startsWith(PARA)).map((k) => Number(k.slice(PARA.length))).filter(Number.isInteger)
const highest = (keys: string[]) => Math.max(0, ...paraNumbers(keys))
const allLines = (d: SlotDoc) => d.sections.flatMap((s) => s.entries.flatMap((e) => [e.heading, e.paragraph, ...e.bullets])).filter((l): l is SlotLine => !!l)

/**
 * What one document shows: its lines and the default text of each slot (generated, else what the facts say). A letter the
 * user wrote or generated is a body of `para:<n>` paragraphs between the greeting and the sign-off, as the backend saves it
 * (domain/slots.with_paragraphs); the template's own sentences and bullets are not part of such a letter.
 */
export function shown(preview: PreviewDoc, d: Pick<DocDraft, 'generated' | 'overrides'>, kind: DocKind): { doc: SlotDoc; defaults: Record<string, string>; wrote: boolean } {
  const base = slotDoc(preview)
  const defaults: Record<string, string> = Object.fromEntries(allLines(base).map((l) => [l.slot, d.generated[l.slot] ?? l.text]))
  const wrote = kind === 'letter' && (highest(Object.keys(d.generated)) > 0 || highest(Object.keys(d.overrides)) > 0)
  if (!wrote || !base.sections.length) return { doc: base, defaults, wrote: false }
  const template = allLines(base).filter((l) => l.slot.startsWith(PARA))
  const generated = highest(Object.keys(d.generated))
  const count = Math.max(generated || template.length, highest(Object.keys(d.overrides)))
  const entries = base.sections[0].entries
  const field = (e: SlotEntry) => (e.paragraph && !e.bullets.length ? e.paragraph.field : '')
  const body: SlotEntry[] = Array.from({ length: count }, (_, i) => {
    const slot = `${PARA}${i + 1}`
    defaults[slot] = d.generated[slot] ?? (generated ? '' : template[i]?.text ?? '') // generated paragraphs replace the template's, they do not overlay it
    return { heading: null, paragraph: { text: defaults[slot], source_fact_id: null, origin: 'boilerplate', field: '', cites: [], slot }, bullets: [] }
  })
  const kept = [
    ...entries.filter((e) => ['greeting', 'subject'].includes(field(e))),
    ...body,
    ...entries.filter((e) => ['closing', 'title'].includes(field(e))),
  ]
  return { doc: { ...base, sections: [{ title: base.sections[0].title, entries: kept }, ...base.sections.slice(1)] }, defaults, wrote }
}

const filled = (texts: Record<string, string>) => Object.fromEntries(Object.entries(texts).filter(([, v]) => v.trim()))

/**
 * The texts a save sends. `overrides` are the user's own words; `generated` is the writer's text, kept apart so that
 * regenerating replaces it and never an override. A letter written as paragraphs also sends every shown paragraph that has
 * no generated text (the template's sentence) as generated, because the backend takes exactly the `para:<n>` slots it is
 * given as the body.
 */
export function saveTexts(preview: PreviewDoc | undefined, d: Pick<DocDraft, 'generated' | 'overrides'>, kind: DocKind): { overrides: Record<string, string>; generated: Record<string, string> } {
  const overrides = filled(d.overrides)
  const generated = filled(d.generated)
  if (!preview || kind !== 'letter') return { overrides, generated }
  const { doc, defaults, wrote } = shown(preview, d, kind)
  if (!wrote) return { overrides, generated }
  for (const l of allLines(doc).filter((x) => x.slot.startsWith(PARA))) {
    if (!(l.slot in generated) && defaults[l.slot]?.trim()) generated[l.slot] = defaults[l.slot].trim()
  }
  return { overrides, generated }
}
