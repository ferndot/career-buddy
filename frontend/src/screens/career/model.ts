import type { Edge, Fact } from './api'
import { dates } from './dates'

export type Bullet = { id: string; title: string; attributes: Record<string, string>; hidden: boolean }
export type Entry = {
  id: string
  title: string
  org: string
  dates: string
  attributes: Record<string, string>
  bullets: Bullet[]
}
export type Career = { personId: string; name: string; positions: Entry[]; education: Entry[]; skills: string[] }

export const isHidden = (f: { attributes: Record<string, string> }) => f.attributes.hidden === 'true'

const order = (b: Bullet) => {
  const n = Number.parseInt(b.attributes.order ?? '', 10)
  return Number.isNaN(n) ? Infinity : n
}

export { dates }

/** Joins the flat facts and edges into what the screen shows. Hidden positions, schools and skills are left out; hidden bullets stay (unchecked). */
export function buildCareer(facts: Fact[], edges: Edge[]): Career | null {
  const byId = new Map(facts.map((f) => [f.id, f]))
  const out = (id: string, kind: string) =>
    edges.filter((e) => e.source === id && e.kind === kind).flatMap((e) => byId.get(e.target) ?? [])
  const person = facts.find((f) => f.kind === 'Person' && !isHidden(f))
  if (!person) return null

  const entry = (f: Fact, orgKind: string): Entry => ({
    id: f.id,
    title: f.title,
    org: out(f.id, orgKind)[0]?.title ?? f.attributes.school ?? '',
    dates: dates(f.attributes),
    attributes: f.attributes,
    bullets: out(f.id, 'ACHIEVED')
      .map((a) => ({ id: a.id, title: a.title, attributes: a.attributes, hidden: isHidden(a) }))
      .sort((a, b) => order(a) - order(b)),
  })
  const visible = (kind: string) => out(person.id, kind).filter((f) => !isHidden(f))
  return {
    personId: person.id,
    name: person.title,
    positions: visible('HAS_POSITION').map((f) => entry(f, 'AT')),
    education: visible('HAS_EDUCATION').map((f) => entry(f, 'ATTENDED')),
    skills: visible('HAS_SKILL').map((f) => f.title),
  }
}
